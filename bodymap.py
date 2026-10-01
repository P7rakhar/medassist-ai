"""
Body-part x sensation composer.

People rarely use textbook phrases. They say "my stomach hurts", "dard ho raha
hai pet mein" or "सिर में बहुत दर्द". Instead of listing every sentence, we
recognise a BODY PART and a SENSATION anywhere within a short window of each
other (either order, same clause) and map the pair to a symptom in the
knowledge graph. 25 body parts x 11 sensations in English, Hindi and Hinglish.
"""
from __future__ import annotations

from .translit import phonetic_key

WINDOW = 3  # max meaningful words between the body part and the sensation (filler words don't count)

BODY_PARTS = {
    "head":    ["head", "forehead", "sir", "sar", "sirr", "matha", "सिर", "सर", "माथा", "माथे"],
    "stomach": ["stomach", "tummy", "belly", "abdomen", "abdominal", "gut", "pet", "pait", "पेट"],
    "chest":   ["chest", "seena", "seene", "sina", "chhati", "chati", "सीना", "सीने", "छाती"],
    "throat":  ["throat", "gala", "gale", "गला", "गले"],
    "eye":     ["eye", "eyes", "aankh", "aankhen", "aankhon", "ankh", "आंख", "आंखें", "आंखों"],
    "ear":     ["ear", "ears", "kaan", "kan", "कान"],
    "tooth":   ["tooth", "teeth", "daant", "dant", "दांत"],
    "back":    ["back", "lower back", "spine", "kamar", "peeth", "pith", "कमर", "पीठ"],
    "flank":   ["flank", "side of my back", "side of back", "bagal", "pasli", "बगल", "पसली"],
    "joint":   ["joint", "joints", "knee", "knees", "ghutna", "ghutne", "jod", "jodon", "जोड़", "जोड़ों", "घुटना", "घुटने"],
    "leg":     ["leg", "legs", "foot", "feet", "pair", "pairon", "taang", "टांग", "पैर", "पैरों"],
    "arm":     ["arm", "arms", "hand", "hands", "haath", "hath", "बांह", "हाथ"],
    "neck":    ["neck", "gardan", "गर्दन"],
    "body":    ["body", "whole body", "badan", "sharir", "sareer", "बदन", "शरीर"],
    "muscle":  ["muscle", "muscles", "mansapeshi", "मांसपेशी"],
    "skin":    ["skin", "twacha", "chamdi", "त्वचा", "चमड़ी"],
    "urine":   ["urine", "pee", "peeing", "urinating", "urination", "peshab", "pishab", "पेशाब"],
    "heart":   ["heart", "heartbeat", "dil", "dhadkan", "दिल", "धड़कन"],
    "nose":    ["nose", "naak", "नाक"],
    "gums":    ["gums", "gum", "masude", "masudon", "मसूड़े", "मसूड़ों"],
    "face":    ["face", "chehra", "chehre", "mooh", "muh", "चेहरा", "चेहरे", "मुंह"],
    "stool":   ["stool", "stools", "poop", "motion", "latrine", "potty", "mal", "मल", "टट्टी"],
    "vomit":   ["vomit", "ulti", "उल्टी"],
    "cough":   ["cough", "phlegm", "sputum", "khansi", "balgam", "खांसी", "बलगम"],
    "sinus":   ["sinus", "cheeks", "cheek", "gaal", "गाल"],
}

SENSATIONS = {
    "pain":      ["pain", "pains", "ache", "aches", "aching", "hurts", "hurt", "hurting", "paining", "sore", "painful", "dard", "dukh", "peeda", "दर्द", "पीड़ा", "दुख"],
    "burning":   ["burning", "burns", "burn", "jalan", "jal raha", "जलन"],
    "itching":   ["itch", "itchy", "itching", "khujli", "खुजली"],
    "swelling":  ["swelling", "swollen", "puffy", "sujan", "soojan", "सूजन"],
    "bleeding":  ["bleeding", "blood", "bloody", "khoon", "khun", "खून"],
    "heaviness": ["heavy", "heaviness", "tight", "tightness", "pressure", "squeezing", "bharipan", "bhari", "भारीपन", "भारी"],
    "numbness":  ["numb", "numbness", "tingling", "sunn", "jhunjhuni", "सुन्न", "झुनझुनी"],
    "weakness":  ["weak", "weakness", "kamzor", "kamzori", "कमजोर", "कमज़ोरी"],
    "redness":   ["red", "redness", "laal", "लाल"],
    "yellow":    ["yellow", "yellowish", "peela", "peeli", "पीला", "पीली"],
    "racing":    ["racing", "pounding", "fast", "beating fast", "tez", "तेज"],
    "discharge": ["discharge", "pus", "watery", "mavad", "paani", "मवाद", "पानी"],
    "stiffness": ["stiff", "stiffness", "jammed", "akdan", "akad", "अकड़न"],
    "dark":      ["dark", "gehra", "gaadha", "गहरा", "गाढ़ा"],
}

# Words that may sit between a body part and a sensation without breaking the link.
FILLER = {phonetic_key(w) for w in """in the a an my of on at is are was were and or side lower upper left right both very really
so bit little lot much near around area part region whole entire also too feels feel feeling getting got is
mein me ke ki ka ko ho raha rahi rahe hai hain tha bahut thoda se mere meri mera par pe wala wali outof
में के की का को हो रहा रही है हैं बहुत थोड़ा से मेरे मेरी मेरा पर""".split()}

# (body part, sensation) -> symptom ID.  Order-independent.
PAIR_TO_SYMPTOM = {
    ("head", "pain"): "headache", ("head", "heaviness"): "headache",
    ("stomach", "pain"): "abdominal_pain", ("stomach", "burning"): "heartburn", ("stomach", "heaviness"): "bloating", ("stomach", "swelling"): "bloating",
    ("chest", "pain"): "chest_pain", ("chest", "heaviness"): "chest_pain", ("chest", "burning"): "heartburn",
    ("throat", "pain"): "sore_throat", ("throat", "burning"): "sore_throat", ("throat", "itching"): "sore_throat", ("throat", "swelling"): "sore_throat",
    ("eye", "pain"): "eye_pain", ("eye", "redness"): "red_eye", ("eye", "discharge"): "eye_discharge", ("eye", "itching"): "red_eye", ("eye", "yellow"): "yellow_eyes", ("eye", "burning"): "red_eye",
    ("ear", "pain"): "ear_pain", ("ear", "discharge"): "ear_discharge", ("ear", "bleeding"): "ear_discharge",
    ("back", "pain"): "back_pain", ("back", "stiffness"): "back_pain", ("flank", "pain"): "flank_pain",
    ("joint", "pain"): "joint_pain", ("joint", "swelling"): "joint_pain", ("joint", "stiffness"): "joint_pain",
    ("leg", "swelling"): "swelling", ("leg", "numbness"): "limb_weakness", ("leg", "weakness"): "limb_weakness", ("leg", "pain"): "body_ache",
    ("arm", "numbness"): "limb_weakness", ("arm", "weakness"): "limb_weakness", ("arm", "pain"): "body_ache",
    ("neck", "pain"): "neck_pain", ("neck", "stiffness"): "neck_pain",
    ("body", "pain"): "body_ache", ("muscle", "pain"): "body_ache", ("body", "weakness"): "fatigue",
    ("skin", "itching"): "itching", ("skin", "redness"): "rash", ("skin", "swelling"): "swelling", ("skin", "yellow"): "yellow_eyes",
    ("urine", "burning"): "burning_urination", ("urine", "pain"): "burning_urination", ("urine", "bleeding"): "blood_in_urine", ("urine", "yellow"): "dark_urine",
    ("urine", "dark"): "dark_urine",
    ("heart", "racing"): "palpitations", ("heart", "pain"): "chest_pain",
    ("nose", "bleeding"): "nosebleed", ("nose", "discharge"): "runny_nose",
    ("gums", "bleeding"): "bleeding_gums", ("stool", "bleeding"): "bleeding_gums", ("vomit", "bleeding"): "bleeding_gums",
    ("cough", "bleeding"): "coughing_blood",
    ("face", "numbness"): "face_droop", ("face", "weakness"): "face_droop", ("face", "swelling"): "swelling", ("face", "pain"): "facial_pain",
    ("sinus", "pain"): "facial_pain", ("sinus", "heaviness"): "facial_pain",
}
LEFT = {phonetic_key(w) for w in ["left", "baaye", "baye", "bayen", "बाएं", "बाएँ", "बायां"]}
RIGHT = {phonetic_key(w) for w in ["right", "daaye", "daye", "dayen", "दाएं", "दाहिने", "दाहिनी"]}
LOWER = {phonetic_key(w) for w in ["lower", "bottom", "neeche", "niche", "नीचे", "निचले"]}


def _index(groups: dict[str, list[str]]) -> dict[tuple[str, ...], str]:
    idx = {}
    for name, words in groups.items():
        for w in words:
            idx.setdefault(tuple(phonetic_key(t) for t in w.split()), name)
    return idx


PART_INDEX = _index(BODY_PARTS)
SENSE_INDEX = _index(SENSATIONS)


def _scan(keys: list[str], index: dict, blocked: set[int]) -> list[tuple[int, int, str]]:
    out, i = [], 0
    max_n = max(len(k) for k in index)
    while i < len(keys):
        hit = None
        for n in range(min(max_n, len(keys) - i), 0, -1):
            if any(k in blocked for k in range(i, i + n)):
                continue
            key = tuple(keys[i:i + n])
            if key in index:
                hit = (i, i + n, index[key])
                break
        if hit:
            out.append(hit); i = hit[1]
        else:
            i += 1
    return out


def compose(keys: list[str], blocked: set[int]) -> tuple[list[tuple[int, int, str, list[int]]], list[str]]:
    """Return ([(start, end, symptom_id, inner_positions)], unplaced_sensations).

    Unplaced sensations ("I have pain" with no body part) let the app ask "Where is the pain?"."""
    parts = _scan(keys, PART_INDEX, blocked)
    # Sensation words may be shared with an existing phrase: in "head and stomach pain" the
    # lexicon already matched "stomach pain", and "head" still needs that same "pain".
    senses = _scan(keys, SENSE_INDEX, {k for p in parts for k in range(p[0], p[1])})
    results = []
    for ps, pe, part in parts:
        best = None
        for ss, se, sense in senses:          # a sensation may serve several parts: "head and stomach pain"
            lo, hi = (pe, ss) if ss >= pe else (se, ps)
            between = keys[lo:hi]
            if hi < lo or "," in between:
                continue
            gap = sum(1 for k in between if k not in FILLER and not k.isdigit())
            if gap > WINDOW:
                continue
            sid = PAIR_TO_SYMPTOM.get((part, sense))
            if sid and (best is None or gap < best[0] or (gap == best[0] and len(between) < best[4])):
                best = (gap, ss, se, sid, len(between))
        if best:
            _, ss, se, sid, _ = best
            start, end = min(ps, ss), max(pe, se)
            near = set(keys[max(0, start - 3):end])
            if sid == "body_ache" and part == "arm" and near & LEFT:
                sid = "radiating_pain"                           # "pain in my left arm"
            if sid == "abdominal_pain" and near & RIGHT and near & LOWER:
                sid = "lower_right_abd_pain"                     # "pain in the lower right side of my stomach"
            inner = [k for k in range(start, end) if not (ps <= k < pe or ss <= k < se)]
            results.append((start, end, sid, inner))
    used = {k for s, e, *_ in results for k in range(s, e)} | blocked
    unplaced = [sense for ss, se, sense in senses if not any(k in used for k in range(ss, se))]
    return results, unplaced
