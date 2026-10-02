"""
Persistent storage (SQLite, built into Python, so nothing to install).

Tables
  bookings  every appointment made in the app (survives server restarts)
  cases     an ANONYMISED log of each triage: time, area, language, triage level,
            top condition and symptom IDs. No free text, no names, location
            rounded to ~1 km. It powers the public-health Insights page.

Outbreak alert: for infectious conditions, compare the last 3 days in an area with
that area's own baseline over the previous 11 days. Alert when there are at least
5 recent cases and at least 3x the expected number.
"""
from __future__ import annotations

import json
import os
import random
import sqlite3
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

DEFAULT_PATH = Path(os.environ.get("MEDASSIST_DB", Path(__file__).resolve().parent.parent / "medassist.db"))

OUTBREAK_CONDITIONS = {"dengue", "malaria", "chikungunya", "typhoid", "gastroenteritis", "food_poisoning",
                       "viral_hepatitis", "influenza", "conjunctivitis", "chickenpox", "heat_stroke", "common_cold"}
RECENT_DAYS, BASELINE_DAYS = 3, 11
ALERT_MIN_CASES, ALERT_RATIO = 5, 3.0

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
  booking_id TEXT PRIMARY KEY, doctor_id TEXT NOT NULL, doctor_name TEXT, clinic TEXT, area TEXT,
  slot TEXT NOT NULL, slot_end TEXT, mode TEXT, patient_name TEXT, fee INTEGER, video_link TEXT, created_at TEXT,
  note TEXT, status TEXT DEFAULT 'waiting',
  doctor_level TEXT, doctor_condition TEXT, doctor_comment TEXT, reviewed_at TEXT,
  UNIQUE (doctor_id, slot)
);
CREATE TABLE IF NOT EXISTS cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, area TEXT, lat REAL, lon REAL, lang TEXT,
  level TEXT, score INTEGER, top_condition TEXT, symptoms TEXT, simulated INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_cases_ts ON cases (ts);
"""


class Store:
    def __init__(self, path: str | Path = DEFAULT_PATH):
        self.path = str(path)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(SCHEMA)
            # Databases from v0.4 lack the handoff columns: add them in place.
            cols = {r["name"] for r in self.conn.execute("PRAGMA table_info(bookings)")}
            for col, ddl in (("note", "TEXT"), ("status", "TEXT DEFAULT 'waiting'"), ("doctor_level", "TEXT"),
                             ("doctor_condition", "TEXT"), ("doctor_comment", "TEXT"), ("reviewed_at", "TEXT")):
                if col not in cols:
                    self.conn.execute(f"ALTER TABLE bookings ADD COLUMN {col} {ddl}")
            self.conn.commit()

    def close(self) -> None:
        """Close the database file (Windows can't delete a file that is still open)."""
        with self.lock:
            self.conn.close()

    # ------------------------------------------------------------ bookings ---
    def save_booking(self, b: dict) -> None:
        cols = ["booking_id", "doctor_id", "doctor_name", "clinic", "area", "slot", "slot_end", "mode",
                "patient_name", "fee", "video_link", "created_at", "note", "status"]
        values = [json.dumps(b["note"], ensure_ascii=False) if c == "note" and b.get("note") else b.get(c) for c in cols]
        with self.lock:
            self.conn.execute(f"INSERT INTO bookings ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", values)
            self.conn.commit()

    def set_review(self, booking_id: str, level: str, condition: str | None, comment: str | None, when: str) -> None:
        """The doctor's own triage level (and diagnosis) for this patient: a doctor-labelled case."""
        with self.lock:
            self.conn.execute("UPDATE bookings SET doctor_level = ?, doctor_condition = ?, doctor_comment = ?, reviewed_at = ?, "
                              "status = 'seen' WHERE booking_id = ?", (level, condition, comment, when, booking_id))
            self.conn.commit()

    def set_status(self, booking_id: str, status: str) -> None:
        with self.lock:
            self.conn.execute("UPDATE bookings SET status = ? WHERE booking_id = ?", (status, booking_id))
            self.conn.commit()

    def booked_slots(self) -> set[tuple[str, str]]:
        with self.lock:
            return {(r["doctor_id"], r["slot"]) for r in self.conn.execute("SELECT doctor_id, slot FROM bookings")}

    def bookings(self) -> list[dict]:
        with self.lock:
            rows = [dict(r) for r in self.conn.execute("SELECT * FROM bookings ORDER BY created_at DESC")]
        for r in rows:
            r["note"] = json.loads(r["note"]) if r.get("note") else None
            r["status"] = r.get("status") or "waiting"
        return rows

    # --------------------------------------------------------------- cases ---
    def log_case(self, ts: datetime, area: str, lat: float, lon: float, lang: str, level: str,
                 score, top_condition: str | None, symptoms: list[str], simulated: bool = False) -> None:
        with self.lock:
            self.conn.execute(
                "INSERT INTO cases (ts, area, lat, lon, lang, level, score, top_condition, symptoms, simulated) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ts.isoformat(timespec="seconds"), area, round(lat, 2), round(lon, 2), lang, level,
                 score, top_condition, json.dumps(symptoms), int(simulated)))
            self.conn.commit()

    def _cases_since(self, since: datetime) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM cases WHERE ts >= ? ORDER BY ts", (since.isoformat(timespec="seconds"),))
            return [dict(r) for r in rows]

    def insights(self, now: datetime | None = None, days: int = 14) -> dict:
        now = now or datetime.now()
        cases = self._cases_since(now - timedelta(days=days))
        by_day = defaultdict(lambda: Counter())
        sym, cond, levels = Counter(), Counter(), Counter()
        area_total, area_cond = Counter(), defaultdict(Counter)
        for c in cases:
            day = c["ts"][:10]
            by_day[day][c["level"]] += 1
            levels[c["level"]] += 1
            sym.update(json.loads(c["symptoms"] or "[]"))
            if c["top_condition"]:
                cond[c["top_condition"]] += 1
                area_cond[c["area"]][c["top_condition"]] += 1
            area_total[c["area"]] += 1
        series = []
        for i in range(days - 1, -1, -1):
            d = (now - timedelta(days=i)).date().isoformat()
            series.append({"date": d, **{lv: by_day[d].get(lv, 0) for lv in ("LOW", "MODERATE", "HIGH", "UNCERTAIN")}})
        return {
            "window_days": days, "total": len(cases), "simulated": sum(c["simulated"] for c in cases),
            "by_level": dict(levels), "series": series,
            "top_symptoms": sym.most_common(8), "top_conditions": cond.most_common(8),
            "areas": [{"area": a, "total": n, "top": area_cond[a].most_common(3)} for a, n in area_total.most_common()],
            "alerts": self._alerts(cases, now),
        }

    @staticmethod
    def _alerts(cases: list[dict], now: datetime) -> list[dict]:
        recent_from = now - timedelta(days=RECENT_DAYS)
        base_from = recent_from - timedelta(days=BASELINE_DAYS)
        recent, base = Counter(), Counter()
        for c in cases:
            if c["top_condition"] not in OUTBREAK_CONDITIONS:
                continue
            ts = datetime.fromisoformat(c["ts"])
            key = (c["area"], c["top_condition"])
            if ts >= recent_from:
                recent[key] += 1
            elif ts >= base_from:
                base[key] += 1
        alerts = []
        for (area, cid), n in recent.items():
            expected = base[(area, cid)] / BASELINE_DAYS * RECENT_DAYS
            ratio = n / max(expected, 0.5)
            if n >= ALERT_MIN_CASES and ratio >= ALERT_RATIO:
                daily = Counter(c["ts"][:10] for c in cases if c["area"] == area and c["top_condition"] == cid)
                days = [(now - timedelta(days=i)).date().isoformat() for i in range(RECENT_DAYS + BASELINE_DAYS - 1, -1, -1)]
                alerts.append({"area": area, "condition": cid, "recent_cases": n, "expected": round(expected, 1),
                               "ratio": round(ratio, 1), "window_days": RECENT_DAYS,
                               "daily": [{"date": d, "cases": daily.get(d, 0)} for d in days]})
        return sorted(alerts, key=lambda a: -a["ratio"])

    # ----------------------------------------------------------- demo data ---
    def seed_demo(self, engine, now: datetime | None = None, n_background: int = 160, seed: int = 7) -> int:
        """Insert clearly-flagged SIMULATED cases, including a dengue cluster in Dadri, for demos."""
        now = now or datetime.now()
        rng = random.Random(seed)
        common = ["common_cold", "influenza", "gastroenteritis", "gastritis_gerd", "tension_headache", "migraine",
                  "skin_allergy", "uti", "hypertension", "anxiety_depression", "conjunctivitis", "malaria",
                  "typhoid", "dengue", "heat_stroke", "food_poisoning"]
        count = 0

        def add(cid: str, loc: dict, when: datetime):
            nonlocal count
            c = engine.kg.conditions[cid]
            syms = [s for s, w in sorted(c["symptoms"].items(), key=lambda x: -x[1])[:rng.randint(2, 4)]]
            level = "HIGH" if c["severity"] >= 2.6 else "MODERATE" if c["severity"] >= 1.5 else "LOW"
            self.log_case(when, loc["name"], loc["lat"] + rng.uniform(-0.01, 0.01), loc["lon"] + rng.uniform(-0.01, 0.01),
                          rng.choice(["en", "hi", "hinglish"]), level, None, cid, syms, simulated=True)
            count += 1

        for _ in range(n_background):
            when = now - timedelta(days=rng.uniform(0, 14), hours=rng.uniform(0, 12))
            add(rng.choice(common), rng.choice(engine.locations), when)
        dadri = next(l for l in engine.locations if l["id"] == "dadri")
        for _ in range(14):                                    # the cluster the alert should find
            add("dengue", dadri, now - timedelta(days=rng.uniform(0, 2.8)))
        return count

    def clear_demo(self) -> int:
        with self.lock:
            n = self.conn.execute("DELETE FROM cases WHERE simulated = 1").rowcount
            self.conn.commit()
            return n
