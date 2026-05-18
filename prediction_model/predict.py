"""
predict.py — Load the trained model and predict disease from symptoms.

═══════════════════════════════════════════════════════════════════════════════
ROOT CAUSE FIX — WHY MODEL PREDICTED WRONG DISEASES EVERY TIME
═══════════════════════════════════════════════════════════════════════════════

BUG 1 (MOST CRITICAL): "fever" → "mild_fever"  ← WRONG MAPPING
─────────────────────────────────────────────────────────────────
  Old code:  "fever": "mild_fever"
  Problem:   Dataset has mild_fever ONLY for: Chicken pox, hepatitis A, Tuberculosis
             Dataset has high_fever for:      Malaria, Dengue, Typhoid, Pneumonia,
                                              Common Cold, AIDS, Jaundice, and 6 others

  When user types "fever, chills, diarrhoea, vomiting":
    → "fever" mapped to mild_fever
    → mild_fever has NOTHING to do with Malaria in the dataset
    → Model correctly predicts based on just [chills, diarrhoea, vomiting]
    → Those 3 symptoms overlap with Gastroenteritis/Typhoid → wrong prediction

  Fix:  "fever" now maps to "high_fever" (the common/dominant fever type)
        "mild fever" / "low grade fever" → "mild_fever"  (for exact mild cases)

BUG 2: Missing synonyms for dozens of natural user phrases
──────────────────────────────────────────────────────────
  Dataset uses technical names (high_fever, shivering, sweating, nausea).
  Users type everyday words (temperature, trembling, perspiring, feeling sick).
  Many common inputs had no synonym entry → silently dropped → wrong prediction.

  Added 80+ new synonyms covering:
    - shivering / trembling / kaanpna → chills
    - sweating / perspiring / paseena → sweating
    - nausea / feeling sick / ji machalna → nausea
    - temperature / running a fever / bukhar → high_fever
    - blurry vision / aankhein dhundhli → blurred_and_distorted_vision
    - mucus / phlegm / balgam → phlegm
    - and many more (see SYMPTOM_SYNONYMS below)

BUG 3: Fuzzy match cutoff 0.85 was too strict
──────────────────────────────────────────────
  Lowered to 0.82 so typos like "diarrhea" (vs "diarrhoea"), 
  "breathlesness" (vs "breathlessness") are caught.
═══════════════════════════════════════════════════════════════════════════════

Provides:
    predict_disease(user_symptoms: list[str]) -> dict
    get_followup_symptoms(current_symptoms, max_suggestions) -> list
    match_symptoms(user_symptoms) -> (matched, unmatched)
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

# ── Model artifacts — loaded once at import time ───────────────────────────────
_model         = joblib.load(os.path.join(SAVED_DIR, "model.pkl"))
_label_encoder = joblib.load(os.path.join(SAVED_DIR, "label_encoder.pkl"))
_symptoms_list = joblib.load(os.path.join(SAVED_DIR, "symptoms_list.pkl"))
_symptom_index = {s: i for i, s in enumerate(_symptoms_list)}


# ── Master data loaders ────────────────────────────────────────────────────────
def _load_descriptions():
    mapping = {}
    path = os.path.join(MASTER_DIR, "diseases_description.csv")
    try:
        with open(path, "r", encoding="utf-8") as f:
            for row in csv.reader(f):
                if len(row) >= 2:
                    mapping[row[0].strip()] = row[1].strip()
    except FileNotFoundError:
        pass
    return mapping


def _load_precautions():
    mapping = {}
    path = os.path.join(MASTER_DIR, "diseases_precaution.csv")
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # skip header
            for row in reader:
                if len(row) >= 2:
                    mapping[row[0].strip()] = [p.strip() for p in row[1:5] if p.strip()]
    except FileNotFoundError:
        pass
    return mapping


def _load_diet_plans():
    """
    CSV format (diseases_diet.csv):
      Disease, Breakfast, Lunch, Dinner, Foods to Avoid, General Tips
    """
    mapping = {}
    path = os.path.join(MASTER_DIR, "diseases_diet.csv")
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                disease = row.get("Disease", "").strip()
                if not disease:
                    continue
                mapping[disease] = {
                    "breakfast":      row.get("Breakfast", "").strip(),
                    "lunch":          row.get("Lunch", "").strip(),
                    "dinner":         row.get("Dinner", "").strip(),
                    "foods_to_avoid": row.get("Foods to Avoid", "").strip(),
                    "general_tips":   row.get("General Tips", "").strip(),
                }
    except FileNotFoundError:
        pass
    return mapping


_descriptions = _load_descriptions()
_precautions  = _load_precautions()
_diet_plans   = _load_diet_plans()


# ── Symptom normalization (must stay exactly in sync with train_model.py) ──────
def _normalize_symptom(text):
    s = str(text).strip().lower().replace("-", "_")
    s = "_".join(s.split())
    s = re.sub(r"_+", "_", s)
    return s


# ══════════════════════════════════════════════════════════════════════════════
# SYMPTOM SYNONYMS MAP
#
# Maps what users actually type → correct dataset key
#
# CRITICAL RULES:
#   1. "fever" alone → "high_fever"  (most diseases use high_fever)
#   2. "mild fever" / "low grade fever" → "mild_fever"
#   3. Every common natural-language phrase must have an entry here
#
# Dataset symptom keys for reference (all 131):
#   high_fever, mild_fever, chills, shivering, sweating, fatigue, lethargy,
#   nausea, vomiting, diarrhoea, stomach_pain, abdominal_pain, headache,
#   muscle_pain, joint_pain, skin_rash, itching, cough, breathlessness,
#   chest_pain, loss_of_appetite, weight_loss, weight_gain, dehydration,
#   dark_urine, yellowish_skin, yellowing_of_eyes, back_pain, neck_pain,
#   runny_nose, congestion, throat_irritation, polyuria, burning_micturition,
#   phlegm, blood_in_sputum, blurred_and_distorted_vision, and more.
# ══════════════════════════════════════════════════════════════════════════════
SYMPTOM_SYNONYMS = {

    # ════════════════════════════════════════════════════════════════
    # FEVER — BUG FIX: "fever" must map to "high_fever" not "mild_fever"
    # Dataset: high_fever used by Malaria, Dengue, Typhoid, Pneumonia,
    #          Common Cold, AIDS, Jaundice, Impetigo, Bronchial Asthma etc.
    #          mild_fever used ONLY by Chicken pox, hepatitis A, Tuberculosis
    # ════════════════════════════════════════════════════════════════
    "fever":                           "high_fever",   # ← KEY FIX (was "mild_fever")
    "high_fever":                      "high_fever",
    "very_high_fever":                 "high_fever",
    "running_a_fever":                 "high_fever",
    "temperature":                     "high_fever",
    "high_temperature":                "high_fever",
    "tez_bukhar":                      "high_fever",
    "bukhar":                          "high_fever",
    "bukhaar":                         "high_fever",
    "mild_fever":                      "mild_fever",
    "low_grade_fever":                 "mild_fever",
    "slight_fever":                    "mild_fever",
    "hafif_bukhar":                    "mild_fever",
    "low_fever":                       "mild_fever",

    # ════════════════════════════════════════════════════════════════
    # CHILLS / SHIVERING — missing many natural phrases
    # ════════════════════════════════════════════════════════════════
    "chills":                          "chills",
    "feeling_cold":                    "chills",
    "cold_feeling":                    "chills",
    "cold_chills":                     "chills",
    "rigors":                          "chills",
    "shivering":                       "chills",      # dataset has both chills AND shivering
    "trembling":                       "chills",
    "shaking":                         "chills",
    "kaanpna":                         "chills",
    "thithurana":                      "chills",
    "body_shaking":                    "chills",
    "goosebumps":                      "chills",

    # ════════════════════════════════════════════════════════════════
    # SWEATING
    # ════════════════════════════════════════════════════════════════
    "sweating":                        "sweating",
    "excessive_sweating":              "sweating",
    "night_sweats":                    "sweating",
    "perspiring":                      "sweating",
    "perspiration":                    "sweating",
    "paseena":                         "sweating",
    "zyada_paseena":                   "sweating",
    "sweaty":                          "sweating",
    "damp_skin":                       "sweating",

    # ════════════════════════════════════════════════════════════════
    # NAUSEA / FEELING SICK
    # ════════════════════════════════════════════════════════════════
    "nausea":                          "nausea",
    "feeling_nauseous":                "nausea",
    "feeling_sick":                    "nausea",
    "sick_feeling":                    "nausea",
    "queasy":                          "nausea",
    "nauseous":                        "nausea",
    "ji_machalna":                     "nausea",
    "ulti_jaisi_feeling":              "nausea",
    "want_to_vomit":                   "nausea",
    "urge_to_vomit":                   "nausea",
    "motion_sickness":                 "nausea",
    "upset_stomach_feeling":           "nausea",

    # ════════════════════════════════════════════════════════════════
    # VOMITING
    # ════════════════════════════════════════════════════════════════
    "vomiting":                        "vomiting",
    "throwing_up":                     "vomiting",
    "puking":                          "vomiting",
    "vomit":                           "vomiting",
    "ulti":                            "vomiting",
    "ulti_aana":                       "vomiting",
    "being_sick":                      "vomiting",

    # ════════════════════════════════════════════════════════════════
    # DIARRHOEA
    # ════════════════════════════════════════════════════════════════
    "diarrhoea":                       "diarrhoea",
    "diarrhea":                        "diarrhoea",   # American spelling
    "loose_motions":                   "diarrhoea",
    "loose_stools":                    "diarrhoea",
    "watery_stools":                   "diarrhoea",
    "frequent_stools":                 "diarrhoea",
    "running_stomach":                 "diarrhoea",
    "dast":                            "diarrhoea",
    "loose_motion":                    "diarrhoea",
    "motions":                         "diarrhoea",
    "latrine_problem":                 "diarrhoea",

    # ════════════════════════════════════════════════════════════════
    # HEADACHE
    # ════════════════════════════════════════════════════════════════
    "headache":                        "headache",
    "head_pain":                       "headache",
    "head_ache":                       "headache",
    "sir_dard":                        "headache",
    "sar_dard":                        "headache",
    "throbbing_head":                  "headache",
    "migraine":                        "headache",
    "head_pressure":                   "headache",

    # ════════════════════════════════════════════════════════════════
    # FATIGUE / TIREDNESS / THAKAN
    # ════════════════════════════════════════════════════════════════
    "fatigue":                         "fatigue",
    "extreme_fatigue":                 "fatigue",
    "chronic_fatigue":                 "fatigue",
    "always_tired":                    "fatigue",
    "feeling_tired":                   "fatigue",
    "tiredness":                       "fatigue",
    "exhaustion":                      "fatigue",
    "lack_of_energy":                  "fatigue",
    "weakness":                        "fatigue",
    "body_weakness":                   "fatigue",
    "low_energy":                      "fatigue",
    "thakaan":                         "fatigue",
    "thaka_hua":                       "fatigue",
    "kamzori":                         "fatigue",
    "tired":                           "fatigue",
    "very_tired":                      "fatigue",
    "no_energy":                       "fatigue",
    "sluggish":                        "lethargy",
    "sluggishness":                    "lethargy",
    "lethargic":                       "lethargy",
    "laziness":                        "lethargy",
    "aalas":                           "lethargy",

    # ════════════════════════════════════════════════════════════════
    # MUSCLE / BODY PAIN
    # ════════════════════════════════════════════════════════════════
    "muscle_pain":                     "muscle_pain",
    "muscle_ache":                     "muscle_pain",
    "body_ache":                       "muscle_pain",
    "body_pain":                       "muscle_pain",
    "maaspan_mein_dard":               "muscle_pain",
    "pain_in_muscles":                 "muscle_pain",
    "pain_everywhere":                 "muscle_pain",
    "myalgia":                         "muscle_pain",
    "sore_muscles":                    "muscle_pain",

    # ════════════════════════════════════════════════════════════════
    # JOINT PAIN
    # ════════════════════════════════════════════════════════════════
    "joint_pain":                      "joint_pain",
    "joint_ache":                      "joint_pain",
    "jodon_mein_dard":                 "joint_pain",
    "arthralgia":                      "joint_pain",
    "achy_joints":                     "joint_pain",
    "painful_joints":                  "joint_pain",

    # ════════════════════════════════════════════════════════════════
    # STOMACH / ABDOMINAL PAIN
    # ════════════════════════════════════════════════════════════════
    "stomach_pain":                    "stomach_pain",
    "stomach_ache":                    "stomach_pain",
    "tummy_ache":                      "stomach_pain",
    "pet_mein_dard":                   "stomach_pain",
    "pet_dard":                        "stomach_pain",
    "abdominal_pain":                  "abdominal_pain",
    "belly_pain":                      "abdominal_pain",
    "belly_ache":                      "abdominal_pain",
    "pait_dard":                       "abdominal_pain",
    "stomach_cramps":                  "cramps",
    "cramps":                          "cramps",
    "period_cramps":                   "cramps",

    # ════════════════════════════════════════════════════════════════
    # BACK / NECK / CHEST PAIN
    # ════════════════════════════════════════════════════════════════
    "back_pain":                       "back_pain",
    "lower_back_pain":                 "back_pain",
    "upper_back_pain":                 "back_pain",
    "kamar_dard":                      "back_pain",
    "peeth_dard":                      "back_pain",
    "chest_pain":                      "chest_pain",
    "chest_tightness":                 "chest_pain",
    "chest_pressure":                  "chest_pain",
    "seene_mein_dard":                 "chest_pain",
    "seene_mein_jalan":                "chest_pain",
    "heart_pain":                      "chest_pain",
    "neck_pain":                       "neck_pain",
    "neck_ache":                       "neck_pain",
    "gardan_dard":                     "neck_pain",
    "stiff_neck":                      "stiff_neck",
    "neck_stiffness":                  "stiff_neck",
    "knee_pain":                       "knee_pain",
    "knee_ache":                       "knee_pain",
    "ghutne_mein_dard":                "knee_pain",
    "hip_pain":                        "hip_joint_pain",
    "hip_ache":                        "hip_joint_pain",

    # ════════════════════════════════════════════════════════════════
    # COUGH / RESPIRATORY
    # ════════════════════════════════════════════════════════════════
    "cough":                           "cough",
    "dry_cough":                       "cough",
    "wet_cough":                       "cough",
    "persistent_cough":                "cough",
    "khansi":                          "cough",
    "khasi":                           "cough",
    "breathlessness":                  "breathlessness",
    "shortness_of_breath":             "breathlessness",
    "difficulty_breathing":            "breathlessness",
    "hard_to_breathe":                 "breathlessness",
    "cant_breathe":                    "breathlessness",
    "saans_lene_mein_takleef":         "breathlessness",
    "dyspnea":                         "breathlessness",
    "phlegm":                          "phlegm",
    "sputum":                          "phlegm",
    "mucus":                           "phlegm",
    "balgam":                          "phlegm",
    "coughing_up_mucus":               "phlegm",
    "blood_in_sputum":                 "blood_in_sputum",
    "coughing_blood":                  "blood_in_sputum",
    "haemoptysis":                     "blood_in_sputum",
    "bloody_cough":                    "blood_in_sputum",
    "rusty_sputum":                    "rusty_sputum",
    "mucoid_sputum":                   "mucoid_sputum",
    "runny_nose":                      "runny_nose",
    "runny_nose_discharge":            "runny_nose",
    "naak_bagna":                      "runny_nose",
    "nasal_discharge":                 "runny_nose",
    "congestion":                      "congestion",
    "nasal_congestion":                "congestion",
    "blocked_nose":                    "congestion",
    "stuffy_nose":                     "congestion",
    "band_naak":                       "congestion",
    "throat_irritation":               "throat_irritation",
    "sore_throat":                     "throat_irritation",
    "throat_pain":                     "throat_irritation",
    "gala_kharab":                     "throat_irritation",
    "gale_mein_dard":                  "throat_irritation",
    "sinus_pressure":                  "sinus_pressure",
    "sinus_pain":                      "sinus_pressure",

    # ════════════════════════════════════════════════════════════════
    # SKIN
    # ════════════════════════════════════════════════════════════════
    "skin_rash":                       "skin_rash",
    "rash":                            "skin_rash",
    "body_rash":                       "skin_rash",
    "hives":                           "skin_rash",
    "khujli":                          "itching",
    "itching":                         "itching",
    "itchy_skin":                      "itching",
    "skin_itching":                    "itching",
    "scratching":                      "itching",
    "nodal_skin_eruptions":            "nodal_skin_eruptions",
    "raised_skin_bumps":               "nodal_skin_eruptions",
    "skin_nodules":                    "nodal_skin_eruptions",
    "blister":                         "blister",
    "blisters":                        "blister",
    "chale":                           "blister",
    "yellowish_skin":                  "yellowish_skin",
    "yellow_skin":                     "yellowish_skin",
    "jaundice_skin":                   "yellowish_skin",
    "skin_yellowing":                  "yellowish_skin",
    "peeli_twacha":                    "yellowish_skin",
    "yellowing_of_eyes":               "yellowing_of_eyes",
    "yellow_eyes":                     "yellowing_of_eyes",
    "aankhein_peeli":                  "yellowing_of_eyes",
    "skin_peeling":                    "skin_peeling",
    "peeling_skin":                    "skin_peeling",
    "dischromic_patches":              "dischromic_patches",
    "skin_discoloration":              "dischromic_patches",
    "patches_on_skin":                 "dischromic_patches",
    "blackheads":                      "blackheads",
    "pimples":                         "pus_filled_pimples",
    "acne_pimples":                    "pus_filled_pimples",
    "red_spots":                       "red_spots_over_body",
    "red_spots_on_body":               "red_spots_over_body",
    "bruising":                        "bruising",
    "bruises":                         "bruising",
    "neel_padna":                      "bruising",
    "silver_like_dusting":             "silver_like_dusting",
    "scurring":                        "scurring",
    "yellow_crust":                    "yellow_crust_ooze",

    # ════════════════════════════════════════════════════════════════
    # EYES / VISION
    # ════════════════════════════════════════════════════════════════
    "blurred_vision":                  "blurred_and_distorted_vision",
    "blurry_vision":                   "blurred_and_distorted_vision",
    "distorted_vision":                "blurred_and_distorted_vision",
    "double_vision":                   "blurred_and_distorted_vision",
    "cant_see_clearly":                "blurred_and_distorted_vision",
    "dhundhla_dikhna":                 "blurred_and_distorted_vision",
    "aankhein_dhundhli":               "blurred_and_distorted_vision",
    "redness_of_eyes":                 "redness_of_eyes",
    "red_eyes":                        "redness_of_eyes",
    "aankhein_laal":                   "redness_of_eyes",
    "watering_eyes":                   "watering_from_eyes",
    "tears":                           "watering_from_eyes",
    "eye_discharge":                   "watering_from_eyes",
    "visual_disturbances":             "visual_disturbances",
    "vision_problems":                 "visual_disturbances",
    "pain_behind_the_eyes":            "pain_behind_the_eyes",
    "eye_pain":                        "pain_behind_the_eyes",
    "sunken_eyes":                     "sunken_eyes",

    # ════════════════════════════════════════════════════════════════
    # URINATION / PESHAB
    # ════════════════════════════════════════════════════════════════
    "polyuria":                        "polyuria",
    "frequent_urination":              "polyuria",
    "increased_urination":             "polyuria",
    "excessive_urination":             "polyuria",
    "urinating_frequently":            "polyuria",
    "urinating_often":                 "polyuria",
    "need_to_urinate_often":           "polyuria",
    "passing_urine_frequently":        "polyuria",
    "peeing_a_lot":                    "polyuria",
    "bar_bar_peshab":                  "polyuria",
    "baar_baar_peshab":                "polyuria",
    "trouble_urinating":               "burning_micturition",
    "painful_urination":               "burning_micturition",
    "burning_urination":               "burning_micturition",
    "burning_while_urinating":         "burning_micturition",
    "pain_while_urinating":            "burning_micturition",
    "peshab_mein_jalan":               "burning_micturition",
    "burning_sensation_urine":         "burning_micturition",
    "dark_urine":                      "dark_urine",
    "brown_urine":                     "dark_urine",
    "dark_yellow_urine":               "dark_urine",
    "pechla_peshab":                   "dark_urine",
    "yellow_urine":                    "yellow_urine",
    "foul_smelling_urine":             "foul_smell_of_urine",
    "smelly_urine":                    "foul_smell_of_urine",
    "bladder_discomfort":              "bladder_discomfort",
    "bladder_pain":                    "bladder_discomfort",
    "spotting_urination":              "spotting_urination",

    # ════════════════════════════════════════════════════════════════
    # THIRST / PYAAS
    # ════════════════════════════════════════════════════════════════
    "extreme_thirst":                  "increased_appetite",
    "excessive_thirst":                "increased_appetite",
    "increased_thirst":                "increased_appetite",
    "intense_thirst":                  "increased_appetite",
    "always_thirsty":                  "increased_appetite",
    "feeling_thirsty":                 "increased_appetite",
    "very_thirsty":                    "increased_appetite",
    "polydipsia":                      "increased_appetite",
    "bahut_pyaas":                     "increased_appetite",
    "zyada_pyaas":                     "increased_appetite",
    "thirst":                          "increased_appetite",
    "constantly_thirsty":              "increased_appetite",
    "dry_mouth":                       "dehydration",
    "mouth_is_dry":                    "dehydration",
    "dehydration":                     "dehydration",
    "dehydrated":                      "dehydration",

    # ════════════════════════════════════════════════════════════════
    # HUNGER / APPETITE / BHOOK
    # ════════════════════════════════════════════════════════════════
    "excessive_hunger":                "excessive_hunger",
    "intense_hunger":                  "excessive_hunger",
    "extreme_hunger":                  "excessive_hunger",
    "increased_hunger":                "excessive_hunger",
    "always_hungry":                   "excessive_hunger",
    "constant_hunger":                 "excessive_hunger",
    "feeling_hungry":                  "excessive_hunger",
    "bahut_bhook":                     "excessive_hunger",
    "zyada_bhook":                     "excessive_hunger",
    "loss_of_appetite":                "loss_of_appetite",
    "no_appetite":                     "loss_of_appetite",
    "not_feeling_hungry":              "loss_of_appetite",
    "bhook_nahi":                      "loss_of_appetite",
    "bhook_na_lagna":                  "loss_of_appetite",
    "not_hungry":                      "loss_of_appetite",
    "cant_eat":                        "loss_of_appetite",

    # ════════════════════════════════════════════════════════════════
    # WEIGHT
    # ════════════════════════════════════════════════════════════════
    "weight_loss":                     "weight_loss",
    "losing_weight":                   "weight_loss",
    "sudden_weight_loss":              "weight_loss",
    "wajan_kam_hona":                  "weight_loss",
    "weight_gain":                     "weight_gain",
    "gaining_weight":                  "weight_gain",
    "wajan_badna":                     "weight_gain",
    "obesity":                         "obesity",
    "overweight":                      "obesity",

    # ════════════════════════════════════════════════════════════════
    # DIZZINESS / VERTIGO
    # ════════════════════════════════════════════════════════════════
    "dizziness":                       "dizziness",
    "dizzy":                           "dizziness",
    "lightheadedness":                 "dizziness",
    "chakkar_aana":                    "dizziness",
    "chakkar":                         "dizziness",
    "loss_of_balance":                 "loss_of_balance",
    "balance_problems":                "loss_of_balance",
    "unsteadiness":                    "unsteadiness",
    "unsteady":                        "unsteadiness",
    "spinning_movements":              "spinning_movements",
    "vertigo":                         "spinning_movements",
    "room_spinning":                   "spinning_movements",

    # ════════════════════════════════════════════════════════════════
    # MENTAL / MOOD
    # ════════════════════════════════════════════════════════════════
    "anxiety":                         "anxiety",
    "anxious":                         "anxiety",
    "nervousness":                     "anxiety",
    "ghabrahat":                       "anxiety",
    "depression":                      "depression",
    "feeling_depressed":               "depression",
    "sad":                             "depression",
    "mood_swings":                     "mood_swings",
    "irritability":                    "irritability",
    "irritable":                       "irritability",
    "restlessness":                    "restlessness",
    "restless":                        "restlessness",
    "lack_of_concentration":           "lack_of_concentration",
    "difficulty_concentrating":        "lack_of_concentration",
    "brain_fog":                       "lack_of_concentration",
    "altered_sensorium":               "altered_sensorium",
    "confusion":                       "altered_sensorium",
    "disorientation":                  "altered_sensorium",

    # ════════════════════════════════════════════════════════════════
    # LYMPH NODES / SWELLING
    # ════════════════════════════════════════════════════════════════
    "swelled_lymph_nodes":             "swelled_lymph_nodes",
    "swollen_glands":                  "swelled_lymph_nodes",
    "lymph_node_swelling":             "swelled_lymph_nodes",
    "swollen_lymph_nodes":             "swelled_lymph_nodes",
    "swelling_joints":                 "swelling_joints",
    "swollen_joints":                  "swelling_joints",
    "swollen_legs":                    "swollen_legs",
    "leg_swelling":                    "swollen_legs",
    "swollen_extremities":             "swollen_extremeties",
    "swollen_feet":                    "swollen_extremeties",
    "swelling_of_stomach":             "swelling_of_stomach",
    "distended_abdomen":               "distention_of_abdomen",
    "bloated_stomach":                 "distention_of_abdomen",
    "puffy_face":                      "puffy_face_and_eyes",
    "face_swelling":                   "puffy_face_and_eyes",

    # ════════════════════════════════════════════════════════════════
    # LIVER / JAUNDICE related
    # ════════════════════════════════════════════════════════════════
    "jaundice":                        "yellowish_skin",
    "liver_pain":                      "abdominal_pain",
    "acute_liver_failure":             "acute_liver_failure",
    "dark_yellow_eyes":                "yellowing_of_eyes",
    "malaise":                         "malaise",
    "general_malaise":                 "malaise",
    "feeling_unwell":                  "malaise",
    "generally_unwell":                "malaise",

    # ════════════════════════════════════════════════════════════════
    # HEART / CIRCULATION
    # ════════════════════════════════════════════════════════════════
    "fast_heart_rate":                 "fast_heart_rate",
    "palpitations":                    "palpitations",
    "heart_pounding":                  "palpitations",
    "rapid_heartbeat":                 "fast_heart_rate",
    "tachycardia":                     "fast_heart_rate",
    "dil_tez_dhadakna":                "palpitations",
    "prominent_veins_on_calf":         "prominent_veins_on_calf",
    "varicose_veins":                  "prominent_veins_on_calf",
    "swollen_blood_vessels":           "swollen_blood_vessels",
    "cold_hands_and_feet":             "cold_hands_and_feets",
    "cold_extremities":                "cold_hands_and_feets",

    # ════════════════════════════════════════════════════════════════
    # STOOL / RECTAL
    # ════════════════════════════════════════════════════════════════
    "bloody_stool":                    "bloody_stool",
    "blood_in_stool":                  "bloody_stool",
    "rectal_bleeding":                 "bloody_stool",
    "dark_stool":                      "bloody_stool",
    "constipation":                    "constipation",
    "cant_pass_stool":                 "constipation",
    "qabz":                            "constipation",
    "passage_of_gases":                "passage_of_gases",
    "gas":                             "passage_of_gases",
    "flatulence":                      "passage_of_gases",
    "gas_problem":                     "passage_of_gases",
    "indigestion":                     "indigestion",
    "acidity":                         "acidity",
    "acid_reflux":                     "acidity",
    "heartburn":                       "acidity",
    "stomach_bleeding":                "stomach_bleeding",
    "pain_in_anal_region":             "pain_in_anal_region",
    "anal_pain":                       "pain_in_anal_region",
    "irritation_in_anus":              "irritation_in_anus",

    # ════════════════════════════════════════════════════════════════
    # THYROID / HORMONAL
    # ════════════════════════════════════════════════════════════════
    "enlarged_thyroid":                "enlarged_thyroid",
    "goitre":                          "enlarged_thyroid",
    "thyroid_swelling":                "enlarged_thyroid",
    "abnormal_menstruation":           "abnormal_menstruation",
    "irregular_periods":               "abnormal_menstruation",
    "irregular_menstruation":          "abnormal_menstruation",
    "irregular_sugar_level":           "irregular_sugar_level",
    "blood_sugar_fluctuation":         "irregular_sugar_level",

    # ════════════════════════════════════════════════════════════════
    # NEUROLOGICAL / PARALYSIS
    # ════════════════════════════════════════════════════════════════
    "slurred_speech":                  "slurred_speech",
    "speech_difficulty":               "slurred_speech",
    "paralysis":                       "weakness_of_one_body_side",
    "one_sided_weakness":              "weakness_of_one_body_side",
    "weakness_in_limbs":               "weakness_in_limbs",
    "weak_legs":                       "weakness_in_limbs",
    "weak_arms":                       "weakness_in_limbs",
    "muscle_weakness":                 "muscle_weakness",
    "muscle_wasting":                  "muscle_wasting",
    "movement_stiffness":              "movement_stiffness",
    "stiff_joints":                    "movement_stiffness",
    "loss_of_smell":                   "loss_of_smell",
    "cant_smell":                      "loss_of_smell",
    "coma":                            "coma",
    "unconscious":                     "coma",

    # ════════════════════════════════════════════════════════════════
    # NAILS / HAIR / MISC
    # ════════════════════════════════════════════════════════════════
    "brittle_nails":                   "brittle_nails",
    "breaking_nails":                  "brittle_nails",
    "nail_problems":                   "brittle_nails",
    "inflammatory_nails":              "inflammatory_nails",
    "small_dents_in_nails":            "small_dents_in_nails",
    "nail_pitting":                    "small_dents_in_nails",
    "drying_and_tingling_lips":        "drying_and_tingling_lips",
    "chapped_lips":                    "drying_and_tingling_lips",
    "dry_lips":                        "drying_and_tingling_lips",
    "ulcers_on_tongue":                "ulcers_on_tongue",
    "mouth_ulcers":                    "ulcers_on_tongue",
    "patches_in_throat":               "patches_in_throat",
    "white_patches_throat":            "patches_in_throat",
    "red_sore_around_nose":            "red_sore_around_nose",

    # ════════════════════════════════════════════════════════════════
    # HISTORY / RISK FACTORS
    # ════════════════════════════════════════════════════════════════
    "extra_marital_contacts":          "extra_marital_contacts",
    "unprotected_sex":                 "extra_marital_contacts",
    "family_history":                  "family_history",
    "hereditary":                      "family_history",
    "history_of_alcohol_consumption":  "history_of_alcohol_consumption",
    "alcohol":                         "history_of_alcohol_consumption",
    "drinking_alcohol":                "history_of_alcohol_consumption",
    "receiving_blood_transfusion":     "receiving_blood_transfusion",
    "blood_transfusion":               "receiving_blood_transfusion",
    "receiving_unsterile_injections":  "receiving_unsterile_injections",
    "unsterile_injections":            "receiving_unsterile_injections",
    "toxic_look":                      "toxic_look_(typhos)",
    "typhoid_look":                    "toxic_look_(typhos)",
    "fluid_overload":                  "fluid_overload",
    "continuous_feel_of_urine":        "continuous_feel_of_urine",
    "urge_to_urinate":                 "continuous_feel_of_urine",
    "increased_appetite":              "increased_appetite",
    "painful_walking":                 "painful_walking",
    "walking_pain":                    "painful_walking",
}


# ── Symptom matching ──────────────────────────────────────────────────────────
def match_symptoms(user_symptoms):
    """
    Match user symptom strings to known dataset keys.

    Priority order:
      1. Synonym map  → plain English / Hinglish input → correct dataset key
      2. Exact match  → user already typed the dataset key
      3. Fuzzy match  → cutoff 0.82 (catches typos like "diarrhea" vs "diarrhoea")

    Returns (matched_list, unmatched_list)
    """
    matched   = []
    unmatched = []
    seen      = set()

    for raw in user_symptoms:
        norm   = _normalize_symptom(raw)
        result = None

        # 1. Synonym map (handles natural language + Hinglish)
        if norm in SYMPTOM_SYNONYMS:
            result = SYMPTOM_SYNONYMS[norm]

        # 2. Exact match (user typed dataset key directly)
        elif norm in _symptom_index:
            result = norm

        # 3. Fuzzy match — BUG FIX: lowered cutoff 0.85 → 0.82
        #    Catches: "diarrhea"→"diarrhoea", "breathlesness"→"breathlessness"
        else:
            close = get_close_matches(norm, _symptoms_list, n=1, cutoff=0.82)
            if close:
                result = close[0]

        if result and result in _symptom_index and result not in seen:
            matched.append(result)
            seen.add(result)
        elif not result:
            unmatched.append(raw)

    return matched, unmatched


# ── Main prediction function ───────────────────────────────────────────────────
def predict_disease(user_symptoms):
    """
    Predict a disease from a list of symptom strings.

    Args:
        user_symptoms: list of symptom strings
                       e.g. ["fever", "chills", "diarrhoea", "vomiting"]

    Returns:
        dict with keys:
          - disease            : predicted disease name (str)
          - description        : disease description (str)
          - precautions        : list of precaution strings
          - diet_plan          : dict with breakfast/lunch/dinner/foods_to_avoid/general_tips
          - matched_symptoms   : list of matched symptom keys
          - unmatched_symptoms : list of unmatched raw inputs
          - confidence         : float 0-1
          - top3               : list of {disease, confidence} dicts
          - low_confidence     : bool (True if confidence < 0.50)
    """
    matched, unmatched = match_symptoms(user_symptoms)

    # ── Empty diet plan template (fallback) ───────────────────────────────────
    _empty_diet = {
        "breakfast":      "",
        "lunch":          "",
        "dinner":         "",
        "foods_to_avoid": "",
        "general_tips":   "Eat a balanced diet and consult a nutritionist for personalized advice.",
    }

    if not matched:
        return {
            "disease":            None,
            "description":        "No recognizable symptoms could be identified.",
            "precautions":        [],
            "diet_plan":          _empty_diet,
            "matched_symptoms":   [],
            "unmatched_symptoms": unmatched,
            "confidence":         0.0,
            "top3":               [],
            "low_confidence":     True,
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

    # Top 3 alternatives (shown when confidence is low)
    top3_indices = np.argsort(probabilities)[-3:][::-1]
    top3 = [
        {
            "disease":    _label_encoder.inverse_transform([i])[0],
            "confidence": float(probabilities[i]),
        }
        for i in top3_indices if probabilities[i] > 0.05
    ]

    # low_confidence flag — confidence below 50% is considered unreliable
    low_confidence = confidence < 0.50

    # ── Diet plan lookup ──────────────────────────────────────────────────────
    diet_plan = _diet_plans.get(disease_name) or _diet_plans.get(disease_name.strip())
    if not diet_plan:
        disease_lower = disease_name.strip().lower()
        for key, val in _diet_plans.items():
            if key.strip().lower() == disease_lower:
                diet_plan = val
                break
    diet_plan = diet_plan or _empty_diet

    # ── Precautions lookup ────────────────────────────────────────────────────
    precautions = _precautions.get(disease_name) or _precautions.get(disease_name.strip())
    if not precautions:
        disease_lower = disease_name.strip().lower()
        for key, val in _precautions.items():
            if key.strip().lower() == disease_lower:
                precautions = val
                break
    precautions = precautions or []

    return {
        "disease":            disease_name,
        "description":        _descriptions.get(disease_name, "No description available."),
        "precautions":        precautions,
        "diet_plan":          diet_plan,
        "matched_symptoms":   matched,
        "unmatched_symptoms": unmatched,
        "confidence":         confidence,
        "top3":               top3,
        "low_confidence":     low_confidence,
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
    """Suggest additional symptoms based on the top candidate diseases."""
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
    test_cases = [
        ("Malaria (user's exact bug case)",   ["fever", "chills", "diarrhoea", "vomiting"]),
        ("Malaria (with more symptoms)",       ["fever", "chills", "headache", "nausea", "sweating"]),
        ("Dengue",                             ["fever", "headache", "skin rash", "muscle pain", "joint pain"]),
        ("Typhoid",                            ["fever", "headache", "nausea", "vomiting", "diarrhoea"]),
        ("Pneumonia",                          ["cough", "fever", "breathlessness", "chest pain", "phlegm"]),
        ("Common Cold",                        ["cough", "fever", "runny nose", "sore throat", "fatigue"]),
        ("Diabetes",                           ["frequent urination", "fatigue", "weight loss", "blurry vision"]),
        ("Tuberculosis",                       ["cough", "fever", "fatigue", "chest pain", "blood in sputum"]),
    ]

    print("=" * 70)
    print("  SYMPTOM SYNONYM + PREDICTION TEST")
    print("=" * 70)
    for label, symptoms in test_cases:
        matched, unmatched = match_symptoms(symptoms)
        result = predict_disease(symptoms)
        print(f"\n🔍 {label}")
        print(f"   Input    : {symptoms}")
        print(f"   Matched  : {matched}")
        if unmatched:
            print(f"   Unmatched: {unmatched}")
        print(f"   Predicted: {result['disease']} ({result['confidence']:.0%})")
        if result['top3']:
            top3_str = ", ".join(f"{t['disease']} ({t['confidence']:.0%})" for t in result['top3'][:3])
            print(f"   Top 3    : {top3_str}")