"""
predict.py — Load the trained model and predict disease from symptoms.

Provides:
    predict_disease(user_symptoms: list[str]) -> dict

Returns:
    {
        "disease": str,
        "description": str,
        "precautions": list[str],
        "matched_symptoms": list[str],
        "unmatched_symptoms": list[str],
        "confidence": float,
        "top3": list[dict],
    }
"""

import os
import re
import csv
import numpy as np
import joblib
from difflib import get_close_matches

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SAVED_DIR  = os.path.join(BASE_DIR, "saved_model")
MASTER_DIR = os.path.join(BASE_DIR, "masterdata")

# ── Load model artifacts (once at import time) ────────────────────────────────
_model         = joblib.load(os.path.join(SAVED_DIR, "model.pkl"))
_label_encoder = joblib.load(os.path.join(SAVED_DIR, "label_encoder.pkl"))
_symptoms_list = joblib.load(os.path.join(SAVED_DIR, "symptoms_list.pkl"))
_symptom_index = {s: i for i, s in enumerate(_symptoms_list)}


# ── Load master data ───────────────────────────────────────────────────────────
def _load_descriptions():
    mapping = {}
    path = os.path.join(MASTER_DIR, "diseases_description.csv")
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                mapping[row[0].strip()] = row[1].strip()
    return mapping


def _load_precautions():
    mapping = {}
    path = os.path.join(MASTER_DIR, "diseases_precaution.csv")
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.reader(f):
            if len(row) >= 2:
                mapping[row[0].strip()] = [p.strip() for p in row[1:] if p.strip()]
    return mapping


_descriptions = _load_descriptions()
_precautions  = _load_precautions()


# ── BUG FIX #1: Correct normalizer (matches train_model.py exactly) ───────────
def _normalize_symptom(text):
    """
    Normalize symptom text to dataset key format.
    Must be IDENTICAL to normalize_symptom() in train_model.py.
    """
    s = str(text).strip().lower().replace("-", "_")
    s = "_".join(s.split())       # collapse any whitespace into single _
    s = re.sub(r"_+", "_", s)     # collapse double underscores
    return s


# ── BUG FIX #2: Synonym map ───────────────────────────────────────────────────
# ROOT CAUSE of the wrong Diabetes → Hypothyroidism prediction:
#
#   User typed           Old fuzzy matched to         Correct dataset key
#   "frequent urination" "spotting_urination"  ❌      "polyuria"          ✅
#   "extreme thirst"     "swollen_extremeties" ❌      "dehydration"       ✅
#   "intense hunger"     "excessive_hunger"    ✅ (lucky)
#
# WHY fuzzy matching failed:
#   Fuzzy matching works on CHARACTER SIMILARITY, not MEANING.
#   "frequent_urination" looks like "spotting_urination" (both end in _urination).
#   "extreme_thirst" looks like "swollen_extremeties" (both start with extr...).
#   The dataset uses MEDICAL TERMS (polyuria) but users type PLAIN ENGLISH.
#   Character similarity cannot bridge that gap — a synonym map is required.

SYMPTOM_SYNONYMS = {
    # ── Urination ──────────────────────────────────────────────────────────────
    "frequent_urination":          "polyuria",
    "increased_urination":         "polyuria",
    "excessive_urination":         "polyuria",
    "urinating_frequently":        "polyuria",
    "urinating_often":             "polyuria",
    "need_to_urinate_often":       "polyuria",
    "passing_urine_frequently":    "polyuria",
    "polyuria":                    "polyuria",
    "peeing_a_lot":                "polyuria",
    "urination_problem":           "polyuria",
    "trouble_urinating":           "burning_micturition",
    "painful_urination":           "burning_micturition",
    "burning_urination":           "burning_micturition",
    "burning_while_urinating":     "burning_micturition",

    # ── Thirst ─────────────────────────────────────────────────────────────────
    "extreme_thirst":              "dehydration",
    "excessive_thirst":            "dehydration",
    "increased_thirst":            "dehydration",
    "intense_thirst":              "dehydration",
    "always_thirsty":              "dehydration",
    "feeling_thirsty":             "dehydration",
    "very_thirsty":                "dehydration",
    "polydipsia":                  "dehydration",
    "dry_mouth":                   "dehydration",

    # ── Hunger / Appetite ──────────────────────────────────────────────────────
    "intense_hunger":              "excessive_hunger",
    "extreme_hunger":              "excessive_hunger",
    "increased_hunger":            "excessive_hunger",
    "always_hungry":               "excessive_hunger",
    "constant_hunger":             "excessive_hunger",
    "feeling_hungry":              "excessive_hunger",
    "loss_of_appetite":            "loss_of_appetite",
    "no_appetite":                 "loss_of_appetite",
    "not_feeling_hungry":          "loss_of_appetite",

    # ── Fatigue / Energy ───────────────────────────────────────────────────────
    "extreme_fatigue":             "fatigue",
    "chronic_fatigue":             "fatigue",
    "always_tired":                "fatigue",
    "feeling_tired":               "fatigue",
    "tiredness":                   "fatigue",
    "exhaustion":                  "fatigue",
    "lack_of_energy":              "fatigue",
    "weakness":                    "fatigue",
    "body_weakness":               "fatigue",
    "low_energy":                  "fatigue",
    "sluggish":                    "lethargy",
    "sluggishness":                "lethargy",
    "lethargic":                   "lethargy",

    # ── Pain ───────────────────────────────────────────────────────────────────
    "stomach_ache":                "stomach_pain",
    "tummy_ache":                  "stomach_pain",
    "belly_ache":                  "belly_pain",
    "lower_back_pain":             "back_pain",
    "upper_back_pain":             "back_pain",
    "chest_tightness":             "chest_pain",
    "chest_pressure":              "chest_pain",
    "joint_ache":                  "joint_pain",
    "knee_ache":                   "knee_pain",
    "hip_pain":                    "hip_joint_pain",
    "neck_ache":                   "neck_pain",
    "muscle_ache":                 "muscle_pain",
    "body_ache":                   "muscle_pain",
    "body_pain":                   "muscle_pain",

    # ── Fever / Temperature ────────────────────────────────────────────────────
    "temperature":                 "high_fever",
    "fever":                       "high_fever",
    "running_a_fever":             "high_fever",
    "slight_fever":                "mild_fever",
    "low_grade_fever":             "mild_fever",
    "feeling_cold":                "chills",
    "cold_hands":                  "cold_hands_and_feets",
    "cold_feet":                   "cold_hands_and_feets",

    # ── Skin ───────────────────────────────────────────────────────────────────
    "rash":                        "skin_rash",
    "skin_itching":                "itching",
    "itchy_skin":                  "itching",
    "skin_irritation":             "itching",
    "dry_skin":                    "skin_peeling",
    "peeling_skin":                "skin_peeling",
    "yellow_skin":                 "yellowish_skin",
    "jaundice_skin":               "yellowish_skin",
    "pimples":                     "pus_filled_pimples",
    "acne":                        "blackheads",

    # ── Eyes ───────────────────────────────────────────────────────────────────
    "yellow_eyes":                 "yellowing_of_eyes",
    "red_eyes":                    "redness_of_eyes",
    "blurry_vision":               "blurred_and_distorted_vision",
    "blurred_vision":              "blurred_and_distorted_vision",
    "vision_problems":             "visual_disturbances",
    "watery_eyes":                 "watering_from_eyes",
    "puffy_eyes":                  "puffy_face_and_eyes",

    # ── Digestive ──────────────────────────────────────────────────────────────
    "vomit":                       "vomiting",
    "throwing_up":                 "vomiting",
    "nauseous":                    "nausea",
    "feeling_nauseous":            "nausea",
    "feel_like_vomiting":          "nausea",
    "loose_stools":                "diarrhoea",
    "loose_motion":                "diarrhoea",
    "diarrhea":                    "diarrhoea",
    "stomach_upset":               "indigestion",
    "bloating":                    "distention_of_abdomen",
    "heartburn":                   "acidity",
    "acid_reflux":                 "acidity",
    "gas":                         "passage_of_gases",
    "flatulence":                  "passage_of_gases",
    "constipated":                 "constipation",
    "blood_in_stool":              "bloody_stool",

    # ── Respiratory ────────────────────────────────────────────────────────────
    "shortness_of_breath":         "breathlessness",
    "difficulty_breathing":        "breathlessness",
    "trouble_breathing":           "breathlessness",
    "stuffy_nose":                 "congestion",
    "blocked_nose":                "congestion",
    "nasal_congestion":            "congestion",
    "sneezing":                    "continuous_sneezing",
    "mucus":                       "phlegm",
    "blood_in_cough":              "blood_in_sputum",
    "coughing_blood":              "blood_in_sputum",

    # ── Head / Neuro ───────────────────────────────────────────────────────────
    "migraine":                    "headache",
    "head_pain":                   "headache",
    "head_ache":                   "headache",
    "dizzy":                       "dizziness",
    "vertigo":                     "spinning_movements",
    "difficulty_concentrating":    "lack_of_concentration",
    "poor_concentration":          "lack_of_concentration",
    "numbness":                    "weakness_in_limbs",

    # ── Mood / Mental ──────────────────────────────────────────────────────────
    "sad":                         "depression",
    "depressed":                   "depression",
    "feeling_low":                 "depression",
    "anxious":                     "anxiety",
    "nervous":                     "anxiety",
    "mood_change":                 "mood_swings",
    "irritable":                   "irritability",

    # ── Weight ─────────────────────────────────────────────────────────────────
    "losing_weight":               "weight_loss",
    "unexplained_weight_loss":     "weight_loss",
    "gaining_weight":              "weight_gain",
    "overweight":                  "obesity",
    "obese":                       "obesity",

    # ── Swelling ───────────────────────────────────────────────────────────────
    "swollen_feet":                "swollen_legs",
    "swollen_ankles":              "swollen_legs",
    "leg_swelling":                "swollen_legs",
    "swollen_face":                "puffy_face_and_eyes",
    "enlarged_lymph_nodes":        "swelled_lymph_nodes",
    "swollen_glands":              "swelled_lymph_nodes",
    "swollen_neck":                "enlarged_thyroid",
    "goiter":                      "enlarged_thyroid",

    # ── Heart ──────────────────────────────────────────────────────────────────
    "heart_palpitations":          "palpitations",
    "racing_heart":                "fast_heart_rate",
    "rapid_heartbeat":             "fast_heart_rate",
    "heart_racing":                "fast_heart_rate",

    # ── Other ──────────────────────────────────────────────────────────────────
    "sweating_a_lot":              "sweating",
    "night_sweats":                "sweating",
    "excessive_sweating":          "sweating",
    "stiff_joints":                "movement_stiffness",
    "stiffness":                   "movement_stiffness",
    "difficulty_walking":          "painful_walking",
    "alcohol_history":             "history_of_alcohol_consumption",
    "drinks_alcohol":              "history_of_alcohol_consumption",
    "alcoholic":                   "history_of_alcohol_consumption",
    "blood_sugar_issue":           "irregular_sugar_level",
    "high_blood_sugar":            "irregular_sugar_level",
    "low_blood_sugar":             "irregular_sugar_level",
    "poor_balance":                "unsteadiness",
    "loss_of_balance":             "loss_of_balance",
}


# ── Symptom matching ───────────────────────────────────────────────────────────
def match_symptoms(user_symptoms):
    """
    Match user symptom strings to known dataset symptom keys.

    Priority order:
      1. Synonym map  — plain English → correct medical dataset key
      2. Exact match  — user already used the dataset key
      3. Fuzzy match  — STRICT cutoff 0.85 (only catches minor typos)

    Returns (matched_list, unmatched_list).
    """
    matched   = []
    unmatched = []

    for raw in user_symptoms:
        norm   = _normalize_symptom(raw)
        result = None

        # 1. Synonym map — highest priority
        if norm in SYMPTOM_SYNONYMS:
            result = SYMPTOM_SYNONYMS[norm]

        # 2. Exact match
        elif norm in _symptom_index:
            result = norm

        # 3. Strict fuzzy — ONLY for minor typos, NOT semantic bridging
        #    Old cutoff 0.6 caused:
        #      "frequent_urination" → "spotting_urination"   (wrong!)
        #      "extreme_thirst"     → "swollen_extremeties"  (wrong!)
        else:
            close = get_close_matches(norm, _symptoms_list, n=1, cutoff=0.85)
            if close:
                result = close[0]

        if result and result in _symptom_index:
            matched.append(result)
        else:
            unmatched.append(raw)

    return list(set(matched)), unmatched


# ── Main prediction function ───────────────────────────────────────────────────
def predict_disease(user_symptoms):
    """
    Predict disease from a list of symptom strings.

    Args:
        user_symptoms: list of symptom strings
                       e.g. ["frequent urination", "extreme thirst", "fatigue"]

    Returns:
        dict with: disease, description, precautions,
                   matched_symptoms, unmatched_symptoms, confidence, top3
    """
    matched, unmatched = match_symptoms(user_symptoms)

    if not matched:
        return {
            "disease":            None,
            "description":        "Could not identify any known symptoms from your input.",
            "precautions":        [],
            "matched_symptoms":   [],
            "unmatched_symptoms": unmatched,
            "confidence":         0.0,
            "top3":               [],
        }

    # Build feature vector
    feature_vector = np.zeros(len(_symptoms_list), dtype=int)
    for s in matched:
        feature_vector[_symptom_index[s]] = 1

    # Predict
    prediction    = _model.predict([feature_vector])[0]
    probabilities = _model.predict_proba([feature_vector])[0]
    confidence    = float(np.max(probabilities))
    disease_name  = _label_encoder.inverse_transform([prediction])[0]

    # Top 3 for low-confidence display
    top3_indices = np.argsort(probabilities)[-3:][::-1]
    top3 = [
        {
            "disease":    _label_encoder.inverse_transform([i])[0],
            "confidence": float(probabilities[i]),
        }
        for i in top3_indices if probabilities[i] > 0.05
    ]

    return {
        "disease":            disease_name,
        "description":        _descriptions.get(disease_name, "No description available."),
        "precautions":        _precautions.get(disease_name, []),
        "matched_symptoms":   matched,
        "unmatched_symptoms": unmatched,
        "confidence":         confidence,
        "top3":               top3,
    }


# ── Disease-Symptom Map ────────────────────────────────────────────────────────
def _load_disease_symptom_map():
    """Build {disease: set(symptoms)} from dataset.csv."""
    import pandas as pd
    data_path = os.path.join(BASE_DIR, "data", "dataset.csv")
    df = pd.read_csv(data_path, header=None)
    disease_map = {}
    for _, row in df.iterrows():
        disease = str(row.iloc[0]).strip()
        if not disease or disease == "nan":
            continue
        symptoms = set()
        for val in row.iloc[1:]:
            s = _normalize_symptom(val)
            if s and s != "nan":
                symptoms.add(s)
        if symptoms:
            disease_map.setdefault(disease, set()).update(symptoms)
    return disease_map


_disease_symptom_map = _load_disease_symptom_map()


# ── Follow-up symptom suggestion ──────────────────────────────────────────────
def get_followup_symptoms(current_symptoms, max_suggestions=5):
    """Return additional symptoms to ask about based on top candidate diseases."""
    if not current_symptoms:
        return []

    feature_vector = np.zeros(len(_symptoms_list), dtype=int)
    for s in current_symptoms:
        if s in _symptom_index:
            feature_vector[_symptom_index[s]] = 1

    probabilities = _model.predict_proba([feature_vector])[0]
    top_indices   = np.argsort(probabilities)[-3:][::-1]
    top_diseases  = _label_encoder.inverse_transform(top_indices)

    current_set  = set(current_symptoms)
    symptom_freq = {}
    for disease in top_diseases:
        for sym in _disease_symptom_map.get(disease, set()):
            if sym not in current_set and sym in _symptom_index:
                symptom_freq[sym] = symptom_freq.get(sym, 0) + 1

    return sorted(symptom_freq, key=lambda s: symptom_freq[s], reverse=True)[:max_suggestions]


# ── Quick test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("TEST 1 — Diabetes symptoms (plain English input)")
    print("=" * 55)
    test1 = ["frequent urination", "extreme thirst", "fatigue", "intense hunger"]
    r1 = predict_disease(test1)
    print(f"Input:       {test1}")
    print(f"Matched:     {r1['matched_symptoms']}")
    print(f"Unmatched:   {r1['unmatched_symptoms']}")
    print(f"Disease:     {r1['disease']}")
    print(f"Confidence:  {r1['confidence']:.1%}")
    print(f"Top 3:       {r1['top3']}")

    print()
    print("=" * 55)
    print("TEST 2 — Fungal infection")
    print("=" * 55)
    r2 = predict_disease(["itching", "skin rash", "nodal skin eruptions"])
    print(f"Disease:    {r2['disease']}")
    print(f"Confidence: {r2['confidence']:.1%}")

    print()
    print("=" * 55)
    print("TEST 3 — Follow-up suggestions for diabetes")
    print("=" * 55)
    print(f"Suggest: {get_followup_symptoms(r1['matched_symptoms'])}")