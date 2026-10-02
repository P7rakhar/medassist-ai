"""
Appointment slots and booking.

Slots are generated from each doctor's weekly sessions. To make the demo
realistic, a deterministic share of slots is marked as already taken
(simulated occupancy). Real bookings made in the app are held in memory; in
production this is a database table plus the clinic's / ABDM's booking API.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta


class SlotScheduler:
    def __init__(self, slot_minutes: int = 20, occupancy: float = 0.35, lead_minutes: int = 15, store=None):
        self.slot = timedelta(minutes=slot_minutes)
        self.occupancy = occupancy
        self.lead = timedelta(minutes=lead_minutes)
        self.store = store                       # SQLite store: bookings survive restarts
        self.booked: set[tuple[str, str]] = store.booked_slots() if store else set()
        self.bookings: dict[str, dict] = {b["booking_id"]: b for b in store.bookings()} if store else {}

    def _simulated_busy(self, doctor_id: str, start: datetime) -> bool:
        h = hashlib.sha1(f"{doctor_id}|{start:%Y-%m-%dT%H:%M}".encode()).digest()
        return h[0] / 255 < self.occupancy

    def free_slots(self, doctor: dict, now: datetime, days_ahead: int = 7, limit: int | None = None) -> list[datetime]:
        out: list[datetime] = []
        earliest = now + self.lead
        for day in range(days_ahead + 1):
            date = (now + timedelta(days=day)).date()
            for sess in doctor["sessions"]:
                if date.weekday() not in sess["days"]:
                    continue
                t = datetime.combine(date, datetime.strptime(sess["start"], "%H:%M").time())
                end = datetime.combine(date, datetime.strptime(sess["end"], "%H:%M").time())
                while t + self.slot <= end + timedelta(minutes=1):
                    key = (doctor["id"], t.isoformat(timespec="minutes"))
                    if t >= earliest and key not in self.booked and not self._simulated_busy(doctor["id"], t):
                        out.append(t)
                        if limit and len(out) >= limit:
                            return sorted(out)
                    t += self.slot
        return sorted(out)

    def next_slot(self, doctor: dict, now: datetime) -> datetime | None:
        slots = self.free_slots(doctor, now, limit=1)
        return slots[0] if slots else None

    def book(self, doctor: dict, slot_iso: str, patient_name: str, mode: str, now: datetime | None = None,
             note: dict | None = None) -> dict:
        now = now or datetime.now()
        start = datetime.fromisoformat(slot_iso)
        if slot_iso not in {s.isoformat(timespec="minutes") for s in self.free_slots(doctor, now)}:
            raise ValueError("Slot is no longer available")
        if mode == "video" and not doctor.get("teleconsult"):
            raise ValueError("This doctor does not offer video consultations")
        self.booked.add((doctor["id"], slot_iso))
        booking_id = "MA-" + secrets.token_hex(3).upper()
        booking = {
            "booking_id": booking_id, "doctor_id": doctor["id"], "doctor_name": doctor["name"],
            "clinic": doctor["clinic"], "area": doctor["area"], "slot": slot_iso,
            "slot_end": (start + self.slot).isoformat(timespec="minutes"),
            "mode": mode, "patient_name": patient_name or "Patient", "fee": doctor["fee"],
            "video_link": f"https://meet.jit.si/MedAssist-{booking_id}-{secrets.token_hex(4)}" if mode == "video" else None,
            "created_at": now.isoformat(timespec="seconds"),
            "note": note, "status": "waiting",        # pre-consultation note for the doctor (handoff.py)
        }
        self.bookings[booking_id] = booking
        if self.store:
            self.store.save_booking(booking)
        return booking

    def set_review(self, booking_id: str, level: str, condition: str | None, comment: str | None,
                   now: datetime | None = None) -> dict:
        b = self.bookings[booking_id]
        when = (now or datetime.now()).isoformat(timespec="seconds")
        b.update({"doctor_level": level, "doctor_condition": condition, "doctor_comment": comment,
                  "reviewed_at": when, "status": "seen"})
        if self.store:
            self.store.set_review(booking_id, level, condition, comment, when)
        return b

    def set_status(self, booking_id: str, status: str) -> dict:
        b = self.bookings[booking_id]
        b["status"] = status
        if self.store:
            self.store.set_status(booking_id, status)
        return b
