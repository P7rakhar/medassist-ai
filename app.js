/* MedAssist AI — front-end (vanilla JS, no build step, works offline). */
"use strict";

const T = {
  en: {
    tagline: "Healthcare guidance in your language", location: "Location", inPerson: "Visit clinic", video: "Video consult",
    askTitle: "How are you feeling?", askHint: "Speak or type in English, Hindi or Hinglish. Mention how long it has lasted.",
    placeholder: "e.g. I have had fever and body ache for 3 days", speak: "Speak", stop: "Stop", age: "Age",
    analyse: "Check symptoms", analysing: "Checking…", tryExample: "Try an example",
    traceTitle: "How the AI reached this result", traceEmpty: "Each step of the analysis pipeline appears here, with its timing.",
    emptyTitle: "Your result will appear here",
    emptyBody: "You'll see the risk level, what to do next, likely causes and doctors you can book — in English or Hindi.",
    lvl_LOW: "Low risk", lvl_MODERATE: "Moderate risk", lvl_HIGH: "High risk", lvl_UNCERTAIN: "Needs a doctor's review",
    riskScore: "risk score", readAloud: "Read aloud", emergencyNote: "Emergency numbers in India — ambulance and police",
    understood: "What we understood", followup: "Do you also have any of these?", followupHint: "Tap to add — the assessment updates instantly.",
    likely: "Possible causes", likelyNote: "Relative match from our medical knowledge graph — not a diagnosis.",
    advice: "What you can do now", doctors: "Recommended doctors",
    formula: "Ranked by match score = 0.30 specialty + 0.20 distance + 0.15 rating + 0.15 availability + 0.10 language + 0.10 cost",
    pickSlot: "Pick a time", yourName: "Your name", cancel: "Cancel", confirm: "Confirm booking", booked: "Booked", done: "Done",
    duration: "Duration", severity: "Severity", temp: "Temperature", ageLbl: "Age", days: "days", hours: "hours",
    sev_severe: "severe", sev_mild: "mild", sev_normal: "not specified",
    noSymptoms: "No symptoms recognised yet. Try describing them differently, or pick from the examples.",
    match: "match", why: "Why this doctor", component: "Factor", value: "Score", weight: "Weight", contrib: "Points", total: "Match score",
    c_specialty: "Specialty match", c_distance: "Distance", c_rating: "Rating (Bayesian)", c_availability: "Availability",
    c_language: "Language", c_cost: "Cost",
    free: "Free", fee: "₹", km: "km", teleOnly: "Video only", er: "24×7 emergency", today: "Today", tomorrow: "Tomorrow",
    next: "Next slot", noSlots: "No free slots this week", book: "Book", speaks: "Speaks",
    bookingFor: "Booking with", needName: "Please enter your name.", needSlot: "Please pick a time.",
    bId: "Booking ID", bDoctor: "Doctor", bWhen: "When", bWhere: "Where", bMode: "Mode", bFee: "Fee", bLink: "Video link",
    micUnsupported: "Voice input needs Google Chrome or Microsoft Edge. You can type instead.",
    listening: "Listening… speak now", micError: "Couldn't hear you. Check microphone permission and try again.",
    serverError: "The MedAssist server isn't responding. Make sure `python run.py` is still running.",
    describeFirst: "Describe your symptoms first — or tap an example.",
    langDetected: "Detected", tokens: "tokens", candidates: "Candidates", redFlags: "Red flags", none: "none",
    ranked: "doctors ranked for", kgStats: (s) => `Knowledge graph: ${s.symptoms} symptoms, ${s.conditions} conditions, ${s.edges} weighted links, ${s.synonyms} phrases in 3 languages.`,
    llmOff: "LLM fallback: off (fully offline)", added: "added",
    soTitle: "Second opinion from a trained model",
    soModel: (m) => `Logistic regression trained on ${m.cases.toLocaleString("en-IN")} public patient descriptions (${m.diseases} diseases); ${Math.round(m.held_out_accuracy * 100)}% correct on descriptions it never saw.`,
    soAgree: "Agrees with the knowledge graph.", soDiffer: "Differs from the knowledge graph. Your doctor will see both.",
    soOutside: "This disease is outside our knowledge graph. Your doctor will see it.", soUnsure: "The model is not confident here.",
    insightsLink: "Health officer insights", questionsTitle: "A few quick questions", questionsHint: "Each answer updates the assessment straight away.",
    startOver: "Start over", yes: "Yes", no: "No", safetyCheck: "Safety check", mostUseful: "Helps narrow it down",
    maybe: "maybe", youSaidYes: "you said yes", notCounted: "Not counted (in the past)", familyHistory: "Family history",
    existing: "Existing conditions", youMentioned: "You mentioned", notUnderstood: "Words not understood",
    st_past: "in the past", st_suspected: "you suspect", st_stated: "you said", st_denied: "you said no",
    painScore: "Pain score", icd: "ICD-10", source: "About this condition",
    listeningLong: "Listening… keep talking. Press Stop when you're done.", stopping: (n) => `Stopping in ${n}s — keep talking to continue`,
    micDenied: "Microphone access is blocked. Click the lock icon next to the address, allow Microphone, then try again.",
    micNetwork: "Voice recognition needs internet. You can type instead.", micNoDevice: "No microphone found. Plug one in or type instead.",
    heard: "Heard so far",
    noteTitle: "Doctor's note", noteHint: "A one-page summary of what you told us, for your doctor or family. It's attached automatically when you book.",
    notePreview: "Preview note", whatsapp: "Send on WhatsApp", print: "Print / save PDF", close: "Close",
    sharedWith: (n) => `Your symptom summary has been shared with ${n}, so the consultation can start straight away.`,
    doctorViewLink: "See what the doctor sees", doctorLink: "Doctor view", simple: "Simple mode",
    consentTitle: "Before you start",
    consentBody: "MedAssist gives guidance, not a diagnosis. What you type or say is analysed only to suggest care. For health trends we keep anonymised data only: no words, no name, area rounded to about 1 km. If you book, your symptom summary is shared with that doctor. Voice is turned into text by your browser's speech service.",
    consentAgree: "I agree", consentGiven: "Consent given", consentHow: "How your data is used",
    consentNeeded: "Please read the note above and tap “I agree” first.", pleaseAnswer: "Please answer:",
  },
  hi: {
    tagline: "आपकी भाषा में स्वास्थ्य मार्गदर्शन", location: "स्थान", inPerson: "क्लिनिक जाएं", video: "वीडियो परामर्श",
    askTitle: "आप कैसा महसूस कर रहे हैं?", askHint: "हिंदी, अंग्रेज़ी या हिंग्लिश में बोलें या लिखें। बताएं कि कब से तकलीफ है।",
    placeholder: "जैसे: मुझे 3 दिन से बुखार और बदन दर्द है", speak: "बोलें", stop: "रोकें", age: "उम्र",
    analyse: "लक्षण जांचें", analysing: "जांच हो रही है…", tryExample: "उदाहरण आज़माएं",
    traceTitle: "AI इस नतीजे तक कैसे पहुंचा", traceEmpty: "विश्लेषण का हर चरण समय के साथ यहां दिखेगा।",
    emptyTitle: "आपका नतीजा यहां दिखेगा",
    emptyBody: "आपको जोखिम का स्तर, आगे क्या करें, संभावित कारण और डॉक्टर दिखेंगे जिनसे आप समय ले सकते हैं।",
    lvl_LOW: "कम जोखिम", lvl_MODERATE: "मध्यम जोखिम", lvl_HIGH: "उच्च जोखिम", lvl_UNCERTAIN: "डॉक्टर की समीक्षा ज़रूरी",
    riskScore: "जोखिम स्कोर", readAloud: "सुनें", emergencyNote: "भारत के आपातकालीन नंबर — एम्बुलेंस और पुलिस",
    understood: "हमने क्या समझा", followup: "क्या इनमें से कुछ और भी है?", followupHint: "जोड़ने के लिए टैप करें — आकलन तुरंत बदलेगा।",
    likely: "संभावित कारण", likelyNote: "हमारे मेडिकल नॉलेज ग्राफ़ से तुलनात्मक मिलान — यह निदान नहीं है।",
    advice: "अभी आप क्या कर सकते हैं", doctors: "सुझाए गए डॉक्टर",
    formula: "मैच स्कोर = 0.30 विशेषज्ञता + 0.20 दूरी + 0.15 रेटिंग + 0.15 उपलब्धता + 0.10 भाषा + 0.10 खर्च",
    pickSlot: "समय चुनें", yourName: "आपका नाम", cancel: "रद्द करें", confirm: "बुकिंग पक्की करें", booked: "बुकिंग पक्की", done: "ठीक है",
    duration: "अवधि", severity: "गंभीरता", temp: "तापमान", ageLbl: "उम्र", days: "दिन", hours: "घंटे",
    sev_severe: "गंभीर", sev_mild: "हल्का", sev_normal: "नहीं बताया",
    noSymptoms: "अभी कोई लक्षण पहचाना नहीं गया। दूसरे शब्दों में बताएं या उदाहरण चुनें।",
    match: "मैच", why: "यह डॉक्टर क्यों", component: "कारक", value: "स्कोर", weight: "भार", contrib: "अंक", total: "मैच स्कोर",
    c_specialty: "विशेषज्ञता मिलान", c_distance: "दूरी", c_rating: "रेटिंग (बेयेसियन)", c_availability: "उपलब्धता",
    c_language: "भाषा", c_cost: "खर्च",
    free: "मुफ्त", fee: "₹", km: "कि.मी.", teleOnly: "केवल वीडियो", er: "24×7 इमरजेंसी", today: "आज", tomorrow: "कल",
    next: "अगला समय", noSlots: "इस हफ्ते कोई समय खाली नहीं", book: "बुक करें", speaks: "भाषाएं",
    bookingFor: "बुकिंग", needName: "कृपया अपना नाम लिखें।", needSlot: "कृपया समय चुनें।",
    bId: "बुकिंग ID", bDoctor: "डॉक्टर", bWhen: "समय", bWhere: "जगह", bMode: "तरीका", bFee: "फीस", bLink: "वीडियो लिंक",
    micUnsupported: "आवाज़ से लिखने के लिए Google Chrome या Microsoft Edge चाहिए। आप टाइप कर सकते हैं।",
    listening: "सुन रहे हैं… अब बोलें", micError: "आवाज़ नहीं सुनाई दी। माइक्रोफ़ोन की अनुमति जांचें।",
    serverError: "MedAssist सर्वर जवाब नहीं दे रहा। देखें कि `python run.py` चल रहा है।",
    describeFirst: "पहले अपने लक्षण बताएं — या कोई उदाहरण चुनें।",
    langDetected: "पहचानी गई भाषा", tokens: "टोकन", candidates: "संभावनाएं", redFlags: "खतरे के संकेत", none: "कोई नहीं",
    ranked: "डॉक्टर रैंक किए गए —", kgStats: (s) => `नॉलेज ग्राफ़: ${s.symptoms} लक्षण, ${s.conditions} बीमारियां, ${s.edges} भारित संबंध, 3 भाषाओं में ${s.synonyms} वाक्यांश।`,
    llmOff: "LLM फॉलबैक: बंद (पूरी तरह ऑफ़लाइन)", added: "जोड़ा गया",
    soTitle: "प्रशिक्षित मॉडल की दूसरी राय",
    soModel: (m) => `${m.cases.toLocaleString("en-IN")} सार्वजनिक मरीज़ विवरणों (${m.diseases} बीमारियां) पर प्रशिक्षित लॉजिस्टिक रिग्रेशन; अनदेखे विवरणों पर ${Math.round(m.held_out_accuracy * 100)}% सही।`,
    soAgree: "नॉलेज ग्राफ़ से मेल खाती है।", soDiffer: "नॉलेज ग्राफ़ से अलग है। डॉक्टर दोनों देखेंगे।",
    soOutside: "यह बीमारी हमारे नॉलेज ग्राफ़ से बाहर है। डॉक्टर इसे देखेंगे।", soUnsure: "मॉडल यहां पक्का नहीं है।",
    insightsLink: "स्वास्थ्य अधिकारी डैशबोर्ड", questionsTitle: "कुछ छोटे सवाल", questionsHint: "हर जवाब से आकलन तुरंत बदलता है।",
    startOver: "फिर से शुरू करें", yes: "हां", no: "नहीं", safetyCheck: "सुरक्षा जांच", mostUseful: "पहचान में मदद करेगा",
    maybe: "शायद", youSaidYes: "आपने हां कहा", notCounted: "गिना नहीं गया (पहले था)", familyHistory: "परिवार में",
    existing: "पहले से बीमारी", youMentioned: "आपने बताया", notUnderstood: "ये शब्द समझ नहीं आए",
    st_past: "पहले", st_suspected: "आपको शक है", st_stated: "आपने कहा", st_denied: "आपने मना किया",
    painScore: "दर्द स्कोर", icd: "ICD-10", source: "इस बीमारी के बारे में",
    listeningLong: "सुन रहे हैं… बोलते रहें। बोल चुकें तो रोकें दबाएं।", stopping: (n) => `${n} सेकंड में रुकेगा — जारी रखने के लिए बोलते रहें`,
    micDenied: "माइक्रोफ़ोन की अनुमति बंद है। पते के पास ताले पर क्लिक करें, माइक्रोफ़ोन चालू करें और फिर कोशिश करें।",
    micNetwork: "आवाज़ पहचानने के लिए इंटरनेट चाहिए। आप टाइप कर सकते हैं।", micNoDevice: "माइक्रोफ़ोन नहीं मिला। टाइप करें।",
    heard: "अब तक सुना",
    noteTitle: "डॉक्टर के लिए नोट", noteHint: "आपने जो बताया उसका एक पेज का सारांश, डॉक्टर या परिवार के लिए। बुकिंग पर यह अपने-आप डॉक्टर को भेजा जाता है।",
    notePreview: "नोट देखें", whatsapp: "WhatsApp पर भेजें", print: "प्रिंट / PDF", close: "बंद करें",
    sharedWith: (n) => `आपके लक्षणों का सारांश ${n} को भेज दिया गया है, ताकि परामर्श तुरंत शुरू हो सके।`,
    doctorViewLink: "डॉक्टर को क्या दिखता है, देखें", doctorLink: "डॉक्टर व्यू", simple: "सरल मोड",
    consentTitle: "शुरू करने से पहले",
    consentBody: "MedAssist मार्गदर्शन देता है, निदान नहीं। आप जो लिखते या बोलते हैं, उसका विश्लेषण सिर्फ़ इलाज सुझाने के लिए होता है। स्वास्थ्य रुझानों के लिए हम केवल गुमनाम डेटा रखते हैं: न आपके शब्द, न नाम, जगह लगभग 1 कि.मी. तक। बुकिंग करने पर आपके लक्षणों का सारांश उसी डॉक्टर को भेजा जाता है। आवाज़ को टेक्स्ट में आपके ब्राउज़र की स्पीच सेवा बदलती है।",
    consentAgree: "मैं सहमत हूं", consentGiven: "सहमति दी गई", consentHow: "आपका डेटा कैसे इस्तेमाल होता है",
    consentNeeded: "कृपया पहले ऊपर दी गई जानकारी पढ़कर “मैं सहमत हूं” दबाएं।", pleaseAnswer: "कृपया जवाब दें:",
  },
};

const EXAMPLES = [
  { en: "Fever and body ache", hi: "बुखार और बदन दर्द", text: "I have had fever and body ache for 3 days" },
  { en: "Hinglish: dengue-like", hi: "हिंग्लिश: डेंगू जैसे लक्षण", text: "mujhe 3 din se tez bukhar hai, aankhon ke peeche dard aur jodon mein dard" },
  { en: "Hindi: stomach upset", hi: "हिंदी: पेट खराब", text: "मुझे दो दिन से पेट दर्द और उल्टी हो रही है, बुखार नहीं है" },
  { en: "Chest pain", hi: "सीने में दर्द", text: "I have severe chest pain spreading to my left arm and I am sweating" },
  { en: "Elderly: dizziness", hi: "बुज़ुर्ग: चक्कर", text: "headache and dizziness since yesterday, I am 67 years old" },
  { en: "Sleep and mood", hi: "नींद और मन", text: "I can't sleep, feeling anxious and sad for 2 weeks" },
  { en: "Pregnancy warning", hi: "गर्भावस्था चेतावनी", text: "I am 7 months pregnant and have headache and swelling in my legs" },
  { en: "Hinglish, mixed", hi: "हिंग्लिश, मिली-जुली", text: "pet mein dard ho raha hai, bukhar nahi hai, shayad bahar ka khana kharab tha" },
  { en: "Unclear", hi: "अस्पष्ट", text: "I just feel weird today" },
];

const COMPONENTS = ["specialty", "distance", "rating", "availability", "language", "cost"];
const SEG_COLORS = ["var(--seg-1)", "var(--seg-2)", "var(--seg-3)", "var(--seg-4)", "var(--seg-5)", "var(--seg-6)"];
const LANG_NAMES = { en: "English", hi: "हिंदी", pa: "ਪੰਜਾਬੀ", bn: "বাংলা", ta: "தமிழ்", te: "తెలుగు", ml: "മലയാളം", mr: "मराठी", gu: "ગુજરાતી", ur: "اردو" };

const state = { ui: "en", mode: "in_person", meta: null, loc: null, last: null, answers: {}, slots: {}, booking: null, voiceLang: "en-IN",
                consented: false, simple: false, lastBody: null };
const $ = (id) => document.getElementById(id);
const t = (k) => (T[state.ui][k] ?? T.en[k] ?? k);
const L = (obj) => (obj ? (state.ui === "hi" ? obj.hi ?? obj.en : obj.en ?? obj.hi) : "");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Per-tab memory for consent and simple mode. Storage can be unavailable (private mode), so never rely on it.
const session = {
  get: (k) => { try { return sessionStorage.getItem(k); } catch { return null; } },
  set: (k, v) => { try { sessionStorage.setItem(k, v); } catch { /* ignore */ } },
};

/* ------------------------------------------------------------ setup --- */
async function init() {
  bindEvents();
  setConsent(session.get("medassist-consent") === "yes");
  setSimple(session.get("medassist-simple") === "yes");
  applyI18n();
  try {
    const res = await fetch("/api/meta");
    state.meta = await res.json();
    const sel = $("location");
    sel.innerHTML = state.meta.locations.map((l) => `<option value="${l.id}">${esc(l.name)}</option>`).join("")
      + `<option value="gps">📍 My current location</option>`;
    state.loc = state.meta.locations[0];
    $("kg-stats").textContent = T[state.ui].kgStats(state.meta.kg) + (state.meta.llm.enabled ? "" : " " + t("llmOff"));
    renderLegend();
  } catch {
    $("mic-status").textContent = t("serverError");
  }
}

function applyI18n() {
  document.documentElement.lang = state.ui;
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const v = T[state.ui][el.dataset.i18n];
    if (typeof v === "string") el.textContent = v;
  });
  document.querySelectorAll("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
  $("examples").innerHTML = EXAMPLES.map((e, i) => `<button type="button" class="chip" data-ex="${i}">${esc(L(e))}</button>`).join("");
  if (state.meta) {
    $("kg-stats").textContent = T[state.ui].kgStats(state.meta.kg) + (state.meta.llm.enabled ? "" : " " + t("llmOff"));
    renderLegend();
  }
  if (state.last) render(state.last);
}

function bindEvents() {
  $("go").addEventListener("click", () => analyse());
  $("text").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) analyse(); });
  $("examples").addEventListener("click", (e) => {
    const b = e.target.closest("[data-ex]"); if (!b) return;
    if (needConsent()) return;
    $("text").value = EXAMPLES[+b.dataset.ex].text; analyse();
  });
  $("consent-ok").addEventListener("click", () => { setConsent(true); $("mic-status").textContent = ""; });
  $("consent-more").addEventListener("click", () => setConsent(false, true));
  $("simple-toggle").addEventListener("click", () => setSimple(!state.simple));
  $("note-preview").addEventListener("click", () => {
    $("note-body").innerHTML = MedNote.render(state.last.handoff, state.ui); $("note-dlg").showModal();
  });
  $("note-print").addEventListener("click", () => MedNote.print(MedNote.render(state.last.handoff, state.ui)));
  $("note-dlg-print").addEventListener("click", () => { $("note-dlg").close(); MedNote.print(MedNote.render(state.last.handoff, state.ui)); });
  $("note-dlg-close").addEventListener("click", () => $("note-dlg").close());
  document.querySelectorAll("[data-ui]").forEach((b) => b.addEventListener("click", () => {
    state.ui = b.dataset.ui; toggleOn("[data-ui]", b);
    setVoiceLang(state.ui === "hi" ? "hi-IN" : "en-IN");
    applyI18n();
  }));
  document.querySelectorAll("[data-voice]").forEach((b) => b.addEventListener("click", () => setVoiceLang(b.dataset.voice)));
  $("restart").addEventListener("click", () => { state.answers = {}; state.slots = {}; analyse(true); });
  document.querySelectorAll("[data-mode]").forEach((b) => b.addEventListener("click", () => {
    state.mode = b.dataset.mode; toggleOn("[data-mode]", b); if (state.last) analyse(true);
  }));
  $("location").addEventListener("change", onLocation);
  $("mic").addEventListener("click", toggleMic);
  $("speak-out").addEventListener("click", speakResult);
  $("questions").addEventListener("click", (e) => {
    const b = e.target.closest("[data-answer]"); if (!b) return;
    const kind = b.dataset.answer;
    if (kind === "symptom") state.answers[b.dataset.id] = b.dataset.value === "yes";
    else if (kind === "location") state.answers[b.dataset.id] = true, state.slots._location = true;
    else if (kind === "slot") {
      const v = b.dataset.value;
      state.slots[b.dataset.slot] = b.dataset.slot === "severity" ? v : Number(v);
    }
    analyse(true);
  });
  $("doctors").addEventListener("click", (e) => {
    const b = e.target.closest("[data-book]"); if (b) openBooking(b.dataset.book);
  });
  $("slot-list").addEventListener("click", (e) => {
    const b = e.target.closest("[data-slot]"); if (!b) return;
    state.booking.slot = b.dataset.slot; toggleOn("#slot-list [data-slot]", b);
  });
  document.querySelectorAll("[data-bmode]").forEach((b) => b.addEventListener("click", () => {
    if (b.disabled) return; state.booking.mode = b.dataset.bmode; toggleOn("[data-bmode]", b);
  }));
  $("confirm-book").addEventListener("click", confirmBooking);
  $("close-done").addEventListener("click", () => $("book-dlg").close());
}

/* ---------------------------------------------- consent, simple mode --- */
function setConsent(yes, reopened = false) {
  state.consented = yes || (reopened && state.consented);
  if (yes) session.set("medassist-consent", "yes");
  $("consent").classList.toggle("agreed", yes);
}

function needConsent() {
  if (state.consented) return false;
  const c = $("consent");
  c.classList.remove("nudge"); void c.offsetWidth; c.classList.add("nudge");
  $("mic-status").textContent = t("consentNeeded");
  c.scrollIntoView({ behavior: "smooth", block: "center" });
  return true;
}

/* Simple mode: large text and buttons, fewer technical details, and every result is read aloud. */
function setSimple(on) {
  state.simple = on;
  session.set("medassist-simple", on ? "yes" : "no");
  document.body.classList.toggle("simple", on);
  $("simple-toggle").setAttribute("aria-pressed", String(on));
}

function toggleOn(selector, active) {
  document.querySelectorAll(selector).forEach((x) => x.classList.toggle("on", x === active));
}

function onLocation() {
  const v = $("location").value;
  if (v === "gps") {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (p) => { state.loc = { id: "gps", name: "My location", lat: p.coords.latitude, lon: p.coords.longitude }; if (state.last) analyse(true); },
      () => { $("location").value = state.meta.locations[0].id; state.loc = state.meta.locations[0]; },
      { timeout: 8000 });
    return;
  }
  state.loc = state.meta.locations.find((l) => l.id === v);
  if (state.last) analyse(true);
}

/* ---------------------------------------------------------- analyse --- */
async function analyse(keep = false) {
  const text = $("text").value.trim();
  if (!keep) { state.answers = {}; state.slots = {}; }          // a new description starts a new conversation
  if (needConsent()) return;
  if (!text && !Object.keys(state.answers).length) { $("mic-status").textContent = t("describeFirst"); $("text").focus(); return; }
  const btn = $("go"); btn.disabled = true; btn.textContent = t("analysing");
  const ageVal = $("age").value;
  const { _location, ...slots } = state.slots;
  const body = { text, lat: state.loc?.lat ?? 28.544, lon: state.loc?.lon ?? 77.333, mode: state.mode,
                 age: ageVal === "" ? null : Number(ageVal), answers: state.answers, slots };
  try {
    const res = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
    state.last = await res.json();
    state.lastBody = body;
    $("mic-status").textContent = "";
    render(state.last);
    if (state.simple) { speakResult(); $("verdict").scrollIntoView({ behavior: "smooth", block: "start" }); }
  } catch (err) {
    $("mic-status").textContent = err instanceof TypeError ? t("serverError") : String(err.message || err);
  } finally {
    btn.disabled = false; btn.textContent = t("analyse");
  }
}

/* ----------------------------------------------------------- render --- */
function render(r) {
  $("empty").hidden = true; $("result").hidden = false;
  const tr = r.triage;

  // Verdict band
  const v = $("verdict"); v.className = "verdict " + tr.level;
  $("v-level").textContent = T[state.ui]["lvl_" + tr.level];
  $("v-level-alt").textContent = T[state.ui === "hi" ? "en" : "hi"]["lvl_" + tr.level];
  $("v-action").textContent = L(tr.action);
  const score = tr.score ?? "?";
  $("v-score").textContent = score;
  $("v-gauge").style.setProperty("--p", (tr.score ?? 0) + "%");
  $("v-emergency").hidden = !tr.emergency;

  // Understood
  const found = r.symptoms.map((s) => `<span class="chip found${s.uncertain ? " maybe" : ""}">${esc(L(s))}${
      s.method === "fuzzy" ? `<small>≈ “${esc(s.matched_text)}”</small>` : ""}${
      s.method === "answer" || s.method === "chip" ? `<small>${t("youSaidYes")}</small>` : ""}${
      s.uncertain ? `<small>${t("maybe")}</small>` : ""}</span>`);
  const neg = r.negated.map((s) => `<span class="chip neg" title="negated">${esc(L(s))}</span>`);
  $("understood").innerHTML = found.concat(neg).join("") || `<span class="hint">${t("noSymptoms")}</span>`;
  const facts = [];
  if (r.duration_days != null) facts.push(`${t("duration")}: ${fmtDuration(r.duration_days)}`);
  facts.push(`${t("severity")}: ${t("sev_" + r.severity)}`);
  if (r.temperature_f != null) facts.push(`${t("temp")}: ${r.temperature_f}°F`);
  if (r.spo2 != null) facts.push(`SpO2: ${r.spo2}%`);
  if (r.age != null) facts.push(`${t("ageLbl")}: ${r.age}`);
  if (r.pain_score != null) facts.push(`${t("painScore")}: ${r.pain_score}/10`);
  $("facts").textContent = facts.join("   |   ");
  const notes = [];
  if (r.historical.length) notes.push([t("notCounted"), r.historical.map(L).map(esc).join(", ")]);
  if (r.risk_factors.length) notes.push([t("existing"), r.risk_factors.map((x) => `${esc(L(x.label))} (+${x.points})`).join(", ")]);
  if (r.family_history.length) notes.push([t("familyHistory"), r.family_history.map(L).map(esc).join(", ")]);
  if (r.conditions_named.length) notes.push([t("youMentioned"), r.conditions_named.map((c) => `${esc(L(c.name))} (${t("st_" + c.status)})`).join(", ")]);
  if (r.not_understood.length) notes.push([t("notUnderstood"), r.not_understood.map((w) => `<span class="unknown">${esc(w)}</span>`).join(" ")]);
  $("context-notes").innerHTML = notes.map(([k, v]) => `<p><span class="note-k">${k}:</span> ${v}</p>`).join("");
  $("reasons").innerHTML = tr.reasons.map((x) =>
    `<li>${esc(L(x))}${x.points ? `<span class="pts">(${x.points > 0 ? "+" : ""}${Math.round(x.points)})</span>` : ""}</li>`).join("");

  // Clarifying questions
  renderQuestions(r);

  // Conditions
  $("conditions-block").hidden = !r.conditions.length;
  $("conditions").innerHTML = r.conditions.map((c) => `
    <li>
      <span class="name">${esc(L(c.name))}<small>${esc(state.ui === "hi" ? c.specialty_hi : c.specialty)}</small></span>
      <span class="pct">${Math.round(c.likelihood * 100)}%</span>
      <span class="bar"><i style="width:${Math.round(c.likelihood * 100)}%"></i></span>
      <span class="why">${c.matched.map(L).map(esc).join(", ")}${c.icd10 ? ` <span class="icd">${t("icd")} ${esc(c.icd10)}</span>` : ""}${
        c.info_source ? ` <a class="src" href="${esc(c.info_source)}" target="_blank" rel="noopener">${t("source")}</a>` : ""}</span>
    </li>`).join("");

  // Second opinion from the trained model (shown under the knowledge graph's ranking, never instead of it)
  const so = r.second_opinion;
  $("second-opinion").hidden = !so;
  if (so) {
    const verdict = !so.confident ? t("soUnsure") : so.agrees === true ? t("soAgree") : so.agrees === false ? t("soDiffer") : t("soOutside");
    $("second-opinion").innerHTML = `<p class="so-title">${t("soTitle")}</p>
      <p class="so-picks">${so.top.filter((x, i) => i === 0 || x.probability >= 0.05).map((x, i) => `<span class="${i ? "" : "so-top"}">${esc(L(x.name))} ${Math.round(x.probability * 100)}%</span>`).join(" · ")}</p>
      <p class="so-verdict ${so.confident && so.agrees === false ? "differ" : so.confident && so.agrees ? "agree" : ""}">${verdict}</p>
      <p class="fine">${esc(T[state.ui].soModel(so.model))}</p>`;
  }

  // Advice
  const top = r.conditions[0];
  $("advice-block").hidden = !top || tr.level === "UNCERTAIN";
  $("advice").textContent = top ? L(top.advice) : "";

  // Doctors
  $("doc-specialty").textContent = L(r.specialty);
  $("doctors").innerHTML = r.doctors.map(doctorRow).join("");
  $("disclaimer").textContent = L(r.disclaimer);

  // Doctor's note: WhatsApp share (wa.me opens WhatsApp with the text ready; the user picks the contact)
  $("note-block").hidden = !r.handoff || !r.symptoms.length;
  if (r.handoff) $("note-wa").href = "https://wa.me/?text=" + encodeURIComponent(r.handoff.text[state.ui] || r.handoff.text.en);

  renderTrace(r);
}

function doctorRow(d) {
  const tags = [];
  tags.push(d.fee === 0 ? `<span class="tag free">${t("free")}</span>` : `<span class="tag">${t("fee")}${d.fee}</span>`);
  if (d.distance_km != null && !(state.last.mode === "video")) tags.push(`<span class="tag">${d.distance_km} ${t("km")}</span>`);
  if (d.tele_only) tags.push(`<span class="tag">${t("teleOnly")}</span>`);
  else if (d.teleconsult) tags.push(`<span class="tag">${t("video")}</span>`);
  if (d.emergency) tags.push(`<span class="tag er">${t("er")}</span>`);
  tags.push(`<span class="tag">★ ${d.rating} (${d.reviews})</span>`);
  tags.push(`<span class="tag">${t("speaks")}: ${d.languages.map((l) => LANG_NAMES[l] || l).join(", ")}</span>`);
  const bar = COMPONENTS.map((k, i) => `<i style="width:${(d.contributions[k] * 100).toFixed(1)}%;background:${SEG_COLORS[i]}" title="${t("c_" + k)}: ${d.contributions[k]}"></i>`).join("");
  const rows = COMPONENTS.map((k) => `<tr><td>${t("c_" + k)}</td><td>${d.components[k].toFixed(2)}</td><td>× ${state.meta?.weights[k] ?? ""}</td><td>${d.contributions[k].toFixed(3)}</td></tr>`).join("");
  return `
  <li>
    ${d.pinned_reason ? `<p class="pinned">${state.ui === "hi" ? "नज़दीकी 24×7 इमरजेंसी" : esc(d.pinned_reason)}</p>` : ""}
    <div>
      <p class="doc-name">${esc(d.name)}</p>
      <p class="doc-meta">${esc(state.ui === "hi" ? d.specialty_hi : d.specialty)}, ${esc(d.clinic)}, ${esc(d.area)}</p>
      <p class="doc-meta">${t("next")}: ${d.next_slot ? fmtSlot(d.next_slot) : t("noSlots")}</p>
      <div class="doc-tags">${tags.join("")}</div>
    </div>
    <div class="doc-score">
      <strong>${Math.round(d.match_score * 100)}</strong><small>/100 ${t("match")}</small><br>
      <button type="button" class="book" data-book="${d.id}" ${d.slots.length ? "" : "disabled"}>${t("book")}</button>
    </div>
    <span class="stack-bar" aria-hidden="true">${bar}</span>
    <details><summary>${t("why")}</summary>
      <table class="breakdown"><thead><tr><th>${t("component")}</th><th>${t("value")}</th><th>${t("weight")}</th><th>${t("contrib")}</th></tr></thead>
      <tbody>${rows}</tbody><tfoot><tr><td>${t("total")}</td><td></td><td></td><td>${d.match_score.toFixed(3)}</td></tr></tfoot></table>
    </details>
  </li>`;
}

function renderQuestions(r) {
  const qs = r.questions || [];
  const answered = Object.keys(state.answers).length + Object.keys(state.slots).length;
  $("questions-block").hidden = !qs.length && !answered;
  $("restart").hidden = !answered;
  const opt = (attrs, label, cls = "chip") => `<button type="button" class="${cls}" ${attrs}>${esc(label)}</button>`;
  $("questions").innerHTML = qs.map((q) => {
    if (q.type === "symptom") {
      const tag = q.reason === "safety" ? `<span class="q-tag safety">${t("safetyCheck")}</span>` : `<span class="q-tag">${t("mostUseful")}</span>`;
      return `<div class="q"><p class="q-text">${tag}${esc(L(q.prompt).replace("{label}", L(q.label)))}</p>
        <div class="q-actions">${opt(`data-answer="symptom" data-id="${q.id}" data-value="yes"`, t("yes"), "yn yes")}${opt(`data-answer="symptom" data-id="${q.id}" data-value="no"`, t("no"), "yn no")}</div></div>`;
    }
    if (q.type === "location") {
      return `<div class="q"><p class="q-text">${esc(L(q.prompt))}</p><div class="chips">${
        q.options.map((o) => opt(`data-answer="location" data-id="${o.symptom}"`, L(o))).join("")}</div></div>`;
    }
    return `<div class="q"><p class="q-text">${esc(L(q.prompt))}</p><div class="chips">${
      q.options.map((o) => opt(`data-answer="slot" data-slot="${q.slot}" data-value="${o.value}"`, L(o))).join("")}</div></div>`;
  }).join("");
}

function renderLegend() {
  $("legend").innerHTML = COMPONENTS.map((k, i) => `<span><i style="background:${SEG_COLORS[i]}"></i>${t("c_" + k)}</span>`).join("");
}

function renderTrace(r) {
  $("trace-empty").hidden = true;
  const sym = (ids) => ids.map((id) => symLabel(id)).join(", ") || t("none");
  const out = {
    1: (o) => `“${o.text.length > 90 ? o.text.slice(0, 90) + "…" : o.text}”`,
    2: (o) => `${t("langDetected")}: ${o.name} (${Math.round(o.confidence * 100)}%)`,
    3: (o) => `${o.count} ${t("tokens")}: [${o.tokens.slice(0, 12).join(", ")}${o.count > 12 ? ", …" : ""}]`,
    4: (o) => [sym(o.symptoms),
               o.uncertain.length ? `maybe: ${sym(o.uncertain)}` : "", o.negated.length ? `not: ${sym(o.negated)}` : "",
               o.historical.length ? `past: ${sym(o.historical)}` : "", o.risk_factors.length ? `risk: ${o.risk_factors.join(", ")}` : "",
               o.context_triggers.length ? `context: ${o.context_triggers.map((c) => `“${c.text}” ${c.category.toLowerCase()}`).join(", ")}` : "",
               o.duration_days != null ? fmtDuration(o.duration_days) : "", o.methods.join(" + "),
               o.not_understood.length ? `not understood: ${o.not_understood.join(", ")}` : "", o.llm || ""].filter(Boolean).join("; "),
    5: (o) => `${o.candidates_scored ?? ""} scored. ${t("candidates")}: ${o.candidates.map((c) => `${c.id} ${Math.round(c.likelihood * 100)}%`).join(", ") || t("none")}; ${t("redFlags")}: ${o.red_flags.join(", ") || t("none")}`,
    6: (o) => `${T[state.ui]["lvl_" + o.level]}${o.score != null ? ` (${o.score}/100)` : ""}`,
    7: (o) => `${o.doctors.length} ${t("ranked")} ${o.specialty}`,
    8: (o) => o.questions.length ? o.questions.map((q) => symLabel(q)).join(", ") : t("none"),
  };
  $("trace").innerHTML = r.trace.map((s, i) =>
    `<li style="animation-delay:${i * 70}ms"><span>${esc(s.name)}</span><span class="ms">${s.ms} ms</span><span class="out">${esc(out[s.step](s.output))}</span></li>`
  ).join("") + `<li style="animation-delay:${r.trace.length * 70}ms;counter-increment:none" class="total"><span><strong>Total</strong></span><span class="ms"><strong>${r.total_ms} ms</strong></span></li>`;
}

function symLabel(id) {
  const s = state.meta?.symptoms.find((x) => x.id === id);
  return s ? L(s) : id;
}

function fmtDuration(d) {
  if (d < 1) return `${Math.round(d * 24)} ${t("hours")}`;
  return `${+d.toFixed(1)} ${t("days")}`;
}

function fmtSlot(iso) {
  const d = new Date(iso);
  const now = new Date();
  const tom = new Date(now); tom.setDate(now.getDate() + 1);
  const time = d.toLocaleTimeString(state.ui === "hi" ? "hi-IN" : "en-IN", { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return `${t("today")}, ${time}`;
  if (d.toDateString() === tom.toDateString()) return `${t("tomorrow")}, ${time}`;
  return d.toLocaleDateString(state.ui === "hi" ? "hi-IN" : "en-IN", { weekday: "short", day: "numeric", month: "short" }) + ", " + time;
}

/* ---------------------------------------------------------- booking --- */
function openBooking(id) {
  const d = state.last.doctors.find((x) => x.id === id);
  state.booking = { doctor: d, slot: null, mode: state.mode === "video" && d.teleconsult ? "video" : (d.tele_only ? "video" : "in_person") };
  $("book-title").textContent = `${t("bookingFor")} ${d.name}`;
  $("book-sub").textContent = `${state.ui === "hi" ? d.specialty_hi : d.specialty}, ${d.clinic}`;
  $("slot-list").innerHTML = d.slots.map((s) => `<button type="button" data-slot="${s}">${fmtSlot(s)}</button>`).join("");
  document.querySelectorAll("[data-bmode]").forEach((b) => {
    b.disabled = (b.dataset.bmode === "video" && !d.teleconsult) || (b.dataset.bmode === "in_person" && d.tele_only);
    b.classList.toggle("on", b.dataset.bmode === state.booking.mode);
  });
  $("book-error").textContent = "";
  $("book-form").hidden = false; $("book-done").hidden = true;
  $("book-dlg").showModal();
}

async function confirmBooking() {
  const b = state.booking, name = $("pname").value.trim();
  if (!b.slot) { $("book-error").textContent = t("needSlot"); return; }
  if (!name) { $("book-error").textContent = t("needName"); $("pname").focus(); return; }
  try {
    const res = await fetch("/api/book", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ doctor_id: b.doctor.id, slot: b.slot, patient_name: name, mode: b.mode, case: state.lastBody }) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    const rows = [
      [t("bId"), esc(data.booking_id)], [t("bDoctor"), esc(data.doctor_name)], [t("bWhen"), fmtSlot(data.slot)],
      [t("bWhere"), esc(data.mode === "video" ? t("video") : `${data.clinic}, ${data.area}`)],
      [t("bFee"), data.fee === 0 ? t("free") : `₹${data.fee}`],
    ];
    if (data.video_link) rows.push([t("bLink"), `<a href="${data.video_link}" target="_blank" rel="noopener">${esc(data.video_link)}</a>`]);
    $("book-summary").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
    $("book-shared").textContent = data.note ? T[state.ui].sharedWith(data.doctor_name) : "";
    $("open-doctor-view").href = `doctor.html?doctor=${encodeURIComponent(data.doctor_id)}&booking=${encodeURIComponent(data.booking_id)}`;
    $("book-form").hidden = true; $("book-done").hidden = false;
    analyse(true);  // refresh slots so the booked one disappears
  } catch (err) {
    $("book-error").textContent = String(err.message || err);
  }
}

/* ------------------------------------------------------------ voice --- */
/*
 * Robust voice input.
 * Chrome's recogniser ends a session after a pause or a time limit even with continuous = true,
 * so we keep our own transcript and quietly start a new session until the user presses Stop,
 * or until there has been no speech for SILENCE_MS (with a visible countdown first).
 */
const SILENCE_MS = window.MEDASSIST_SILENCE_MS || 8000;
// Phones: the mic can serve only one listener, and Android Chrome's continuous mode repeats or drops text.
// So on phones we use short single-utterance sessions (continuous = false) and our own restart loop.
const IS_MOBILE = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent);
const voice = { rec: null, wanted: false, finalText: "", interim: "", lastHeard: 0, started: 0, timer: null,
                restarts: [], audio: null, raf: 0 };

function setVoiceLang(lang) {
  state.voiceLang = lang;
  document.querySelectorAll("[data-voice]").forEach((b) => b.classList.toggle("on", b.dataset.voice === lang));
}

function toggleMic() {
  if (voice.wanted) { stopVoice(); return; }
  if (needConsent()) return;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { $("mic-status").textContent = t("micUnsupported"); return; }
  voice.wanted = true;
  voice.error = false;
  voice.finalText = $("text").value.trim();
  voice.interim = "";
  voice.lastHeard = voice.started = Date.now();
  voice.restarts = [];
  $("mic").setAttribute("aria-pressed", "true");
  $("mic").querySelector("span").textContent = t("stop");
  $("mic-status").textContent = t("listeningLong");
  $("live").hidden = false;
  renderLive();
  openSession(SR);
  voice.timer = setInterval(tickVoice, 250);
}

function openSession(SR) {
  const rec = new SR();
  rec.lang = state.voiceLang;
  rec.continuous = !IS_MOBILE;
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  rec.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const res = e.results[i];
      const said = res[0].transcript.trim();
      if (res.isFinal) {
        if (said && !voice.finalText.endsWith(said)) voice.finalText = joinText(voice.finalText, said);  // Android can repeat a final result
      } else interim += res[0].transcript;
    }
    voice.interim = interim.trim();
    voice.lastHeard = Date.now();
    showHearing();
    renderLive();
  };
  rec.onerror = (e) => {
    const fatal = { "not-allowed": "micDenied", "service-not-allowed": "micDenied", network: "micNetwork", "audio-capture": "micNoDevice" };
    if (fatal[e.error]) { voice.wanted = false; voice.error = true; $("mic-status").textContent = t(fatal[e.error]); }
    // "no-speech" and "aborted" are normal during pauses: onend restarts the session.
  };
  rec.onend = () => {
    voice.rec = null;
    if (voice.interim) { voice.finalText = joinText(voice.finalText, voice.interim); voice.interim = ""; }
    if (!voice.wanted) { finishVoice(); return; }
    const now = Date.now();
    voice.restarts = voice.restarts.filter((x) => now - x < 10000).concat(now);
    if (voice.restarts.length > 12) { voice.wanted = false; voice.error = true; $("mic-status").textContent = t("micError"); finishVoice(); return; }
    setTimeout(() => { if (voice.wanted && !voice.rec) openSession(SR); }, 120);
  };
  voice.rec = rec;
  try { rec.start(); } catch { /* already started */ }
}

function tickVoice() {
  const silent = Date.now() - voice.lastHeard;
  const secs = Math.floor((Date.now() - voice.started) / 1000);
  const left = Math.ceil((SILENCE_MS - silent) / 1000);
  $("live-meta").textContent = `${String(Math.floor(secs / 60)).padStart(1, "0")}:${String(secs % 60).padStart(2, "0")}`;
  $("mic-status").textContent = silent > SILENCE_MS - 3000 ? T[state.ui].stopping(Math.max(left, 0)) : t("listeningLong");
  if (silent >= SILENCE_MS) stopVoice();
}

function stopVoice() {
  voice.wanted = false;
  clearInterval(voice.timer);
  if (voice.rec) { try { voice.rec.stop(); } catch { finishVoice(); } } else finishVoice();
}

function finishVoice() {
  clearInterval(voice.timer);
  if (voice.interim) { voice.finalText = joinText(voice.finalText, voice.interim); voice.interim = ""; }
  $("text").value = voice.finalText;
  $("mic").setAttribute("aria-pressed", "false");
  $("mic").querySelector("span").textContent = t("speak");
  $("live").hidden = true;
  if (!voice.error) $("mic-status").textContent = "";     // keep error messages visible
  if (voice.finalText.trim()) analyse();
}

function joinText(a, b) {
  b = (b || "").trim();
  return !b ? a : a ? `${a} ${b}` : b;
}

function renderLive() {
  $("live-final").textContent = voice.finalText;
  $("live-interim").textContent = voice.interim;
  $("text").value = joinText(voice.finalText, voice.interim);
}

/* The level bars animate when speech arrives. We deliberately do NOT open the microphone a second time
   (getUserMedia) for a real level meter: on phones that blocks the speech recogniser. */
function showHearing() {
  const live = $("live");
  live.classList.add("hearing");
  clearTimeout(voice.hearingTimer);
  voice.hearingTimer = setTimeout(() => live.classList.remove("hearing"), 700);
}

function speakResult() {
  if (!state.last || !("speechSynthesis" in window)) return;
  const r = state.last, tr = r.triage;
  const parts = [T[state.ui]["lvl_" + tr.level] + ".", L(tr.action)];
  if (r.conditions[0] && tr.level !== "UNCERTAIN") parts.push(L(r.conditions[0].name) + ".", L(r.conditions[0].advice));
  const q = (r.questions || [])[0];
  if (state.simple && q) parts.push(t("pleaseAnswer"), L(q.prompt).replace("{label}", L(q.label)));
  const u = new SpeechSynthesisUtterance(parts.join(" "));
  const lang = state.ui === "hi" ? "hi-IN" : "en-IN";
  u.lang = lang;
  const voice = speechSynthesis.getVoices().find((v) => v.lang === lang) || speechSynthesis.getVoices().find((v) => v.lang.startsWith(lang.slice(0, 2)));
  if (voice) u.voice = voice;
  u.rate = 0.95;
  speechSynthesis.cancel();
  speechSynthesis.speak(u);
}

init();
