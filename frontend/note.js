/* MedAssist AI — renders the doctor handoff note (shared by the patient app and the doctor view). */
"use strict";

window.MedNote = (() => {
  const H = {
    en: {
      title: "Symptom summary for the doctor", symptoms: "Symptoms", possible: "possible", denied: "Says no to",
      past: "In the past only", risk: "Existing conditions", family: "Family history", details: "Details",
      duration: "Duration", severity: "Severity", temp: "Temperature", age: "Age", pain: "Pain", days: "days", hours: "hours",
      answers: "Follow-up answers", yes: "yes", no: "no", causes: "Possible causes to consider", specialty: "Suggested specialty",
      words: "Patient's own words", asked: "asked", why: "Why this triage level", generated: "Generated", language: "Language",
      emergency: "Emergency: call 112 / 108 now", none: "none", sev: { severe: "severe", mild: "mild" },
      lvl: { LOW: "Low risk", MODERATE: "Moderate risk", HIGH: "High risk", UNCERTAIN: "Needs a doctor's review" },
    },
    hi: {
      title: "डॉक्टर के लिए लक्षणों का सारांश", symptoms: "लक्षण", possible: "शायद", denied: "इनसे मना किया",
      past: "सिर्फ़ पहले था", risk: "पहले से बीमारी", family: "परिवार में", details: "विवरण",
      duration: "अवधि", severity: "गंभीरता", temp: "तापमान", age: "उम्र", pain: "दर्द", days: "दिन", hours: "घंटे",
      answers: "सवालों के जवाब", yes: "हां", no: "नहीं", causes: "संभावित कारण", specialty: "सुझाई गई विशेषज्ञता",
      words: "मरीज़ के अपने शब्द", asked: "पूछा गया", why: "यह स्तर क्यों", generated: "बनाया गया", language: "भाषा",
      emergency: "आपातकाल: अभी 112 / 108 पर कॉल करें", none: "कोई नहीं", sev: { severe: "गंभीर", mild: "हल्का" },
      lvl: { LOW: "कम जोखिम", MODERATE: "मध्यम जोखिम", HIGH: "उच्च जोखिम", UNCERTAIN: "डॉक्टर की समीक्षा ज़रूरी" },
    },
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function render(n, lang = "en") {
    const h = H[lang] || H.en;
    const L = (o) => esc(o ? (o[lang] ?? o.en ?? o.id) : "");
    const tr = n.triage;
    const row = (k, v) => (v ? `<dt>${k}</dt><dd>${v}</dd>` : "");
    const chips = (xs, cls = "") => xs.map((x) => `<span class="nchip ${cls}">${L(x)}${x.possible ? ` <small>${h.possible}</small>` : ""}${
      x.asked ? ` <small>${h.asked}</small>` : ""}</span>`).join("");
    const d = n.details || {};
    const det = [];
    if (d.duration_days != null) det.push(`${h.duration}: ${d.duration_days < 1 ? Math.round(d.duration_days * 24) + " " + h.hours : +(+d.duration_days).toFixed(1) + " " + h.days}`);
    if (h.sev[d.severity]) det.push(`${h.severity}: ${h.sev[d.severity]}`);
    if (d.temperature_f != null) det.push(`${h.temp}: ${d.temperature_f}°F`);
    if (d.age != null) det.push(`${h.age}: ${d.age}`);
    if (d.pain_score != null) det.push(`${h.pain}: ${d.pain_score}/10`);
    return `
      <article class="note">
        <header class="note-head ${esc(tr.level)}">
          <div><p class="note-kicker">MedAssist AI · ${h.title}</p>
          <p class="note-level">${h.lvl[tr.level] || esc(tr.level)}${tr.score != null ? ` <span>${tr.score}/100</span>` : ""}</p></div>
          ${tr.emergency ? `<p class="note-emergency">⚠ ${h.emergency}</p>` : ""}
        </header>
        <dl class="note-grid">
          ${row(h.symptoms, n.symptoms.length ? chips(n.symptoms) : h.none)}
          ${row(h.denied, n.denied.length ? chips(n.denied, "neg") : "")}
          ${row(h.past, n.past.length ? chips(n.past, "past") : "")}
          ${row(h.risk, n.risk_factors.map(L).join(", "))}
          ${row(h.family, n.family_history.map(L).join(", "))}
          ${row(h.details, det.join(" · "))}
          ${row(h.causes, n.possible_conditions.map((c) => `${L(c)}${c.icd10 ? ` <span class="icd">${esc(c.icd10)}</span>` : ""}`).join(", "))}
          ${row(h.specialty, L(n.specialty))}
          ${row(h.why, `<ul>${tr.reasons.map((r) => `<li>${L(r)}</li>`).join("")}</ul>`)}
          ${row(h.words, n.patient_words ? `<q>${esc(n.patient_words)}</q> <small>· ${esc(n.language)}</small>` : "")}
        </dl>
        <p class="note-notice">${L(n.notice)} · ${h.generated} ${esc(String(n.generated_at).replace("T", " "))}</p>
      </article>`;
  }

  /* Print just the note: copy it into a print-only container, print, then remove it. */
  function print(html) {
    let area = document.getElementById("print-area");
    if (!area) { area = document.createElement("div"); area.id = "print-area"; document.body.appendChild(area); }
    area.innerHTML = html;
    document.body.classList.add("printing");
    const done = () => { document.body.classList.remove("printing"); area.innerHTML = ""; window.removeEventListener("afterprint", done); };
    window.addEventListener("afterprint", done);
    window.print();
  }

  return { render, print, labels: H };
})();
