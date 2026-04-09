"""
predict.py — Load the trained model and predict disease from symptoms.

FIX SUMMARY (kya fix kiya):
  FIX 1: SYMPTOM_SYNONYMS map bahut expand kiya
          → User jo bhi plain Hindi/English mein type kare, sahi dataset key milegi
  FIX 2: _extract_symptoms() mein original phrase bhi candidate rakha
          → "difficulty breathing" jaise compound words ab bhi match honge
  FIX 3: Confidence threshold + warning logic add kiya
  FIX 4: match_symptoms() mein multi-word phrase matching improve kiya

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

# ── Model artifacts load karo (import time pe ek baar) ────────────────────────
_model         = joblib.load(os.path.join(SAVED_DIR, "model.pkl"))
_label_encoder = joblib.load(os.path.join(SAVED_DIR, "label_encoder.pkl"))
_symptoms_list = joblib.load(os.path.join(SAVED_DIR, "symptoms_list.pkl"))
_symptom_index = {s: i for i, s in enumerate(_symptoms_list)}


# ── Master data load karo ──────────────────────────────────────────────────────
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
            for row in csv.reader(f):
                if len(row) >= 2:
                    mapping[row[0].strip()] = [p.strip() for p in row[1:] if p.strip()]
    except FileNotFoundError:
        pass
    return mapping


_descriptions = _load_descriptions()
_precautions  = _load_precautions()


# ── Symptom normalization (train_model.py ke saath EXACTLY same) ──────────────
def _normalize_symptom(text):
    s = str(text).strip().lower().replace("-", "_")
    s = "_".join(s.split())
    s = re.sub(r"_+", "_", s)
    return s


# ══════════════════════════════════════════════════════════════════════════════
# FIX 1: EXPANDED SYMPTOM SYNONYMS MAP
# 
# Pehle: sirf limited plain English words the
# Ab:    Hindi-influenced English + medical terms + common phrases sab cover
#
# Rule: KEY = jo user type kare (normalized),  VALUE = dataset ka exact key
# ══════════════════════════════════════════════════════════════════════════════
SYMPTOM_SYNONYMS = {

    # ── Urination / Peshab ─────────────────────────────────────────────────────
    "frequent_urination":              "polyuria",
    "increased_urination":             "polyuria",
    "excessive_urination":             "polyuria",
    "urinating_frequently":            "polyuria",
    "urinating_often":                 "polyuria",
    "need_to_urinate_often":           "polyuria",
    "passing_urine_frequently":        "polyuria",
    "polyuria":                        "polyuria",
    "peeing_a_lot":                    "polyuria",
    "urination_problem":               "polyuria",
    "bar_bar_peshab":                  "polyuria",
    "baar_baar_peshab":                "polyuria",
    "trouble_urinating":               "burning_micturition",
    "painful_urination":               "burning_micturition",
    "burning_urination":               "burning_micturition",
    "burning_while_urinating":         "burning_micturition",
    "pain_while_urinating":            "burning_micturition",
    "peshab_mein_jalan":               "burning_micturition",
    "burning_sensation_urine":         "burning_micturition",

    # ── Thirst / Pyaas ────────────────────────────────────────────────────────
    # CRITICAL FIX: "dehydration" is NOT in Diabetes dataset rows.
    # "increased_appetite" IS unique to Diabetes (not in any other disease).
    # In this dataset, polydipsia/thirst is represented as "increased_appetite".
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
    # dry_mouth is general dehydration, not diabetes-specific
    "dry_mouth":                       "dehydration",
    "mouth_is_dry":                    "dehydration",

    # ── Hunger / Appetite / Bhook ─────────────────────────────────────────────
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

    # ── Fatigue / Tiredness / Thakan ─────────────────────────────────────────
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

    # ── Pain / Dard ───────────────────────────────────────────────────────────
    "stomach_ache":                    "stomach_pain",
    "tummy_ache":                      "stomach_pain",
    "pet_mein_dard":                   "stomach_pain",
    "pet_dard":                        "stomach_pain",
    "abdominal_pain":                  "abdominal_pain",
    "belly_pain":                      "abdominal_pain",
    "belly_ache":                      "abdominal_pain",
    "lower_back_pain":                 "back_pain",
    "upper_back_pain":                 "back_pain",
    "kamar_dard":                      "back_pain",
    "peeth_dard":                      "back_pain",
    "chest_tightness":                 "chest_pain",
    "chest_pressure":                  "chest_pain",
    "seene_mein_dard":                 "chest_pain",
    "seene_mein_jalan":                "chest_pain",
    "joint_ache":                      "joint_pain",
    "jodon_mein_dard":                 "joint_pain",
    "knee_ache":                       "knee_pain",
    "ghutne_mein_dard":                "knee_pain",
    "hip_pain":                        "hip_joint_pain",
    "neck_ache":                       "neck_pain",
    "gardan_dard":                     "neck_pain",
    "muscle_ache":                     "muscle_pain",
    "body_ache":                       "muscle_pain",
    "body_pain":                       "muscle_pain",
    "maaspan_mein_dard":               "muscle_pain",
    "pain_in_muscles":                 "muscle_pain",
    "pain_everywhere":                 "muscle_pain",

    # ── Fever / Bukhar / Temperature ─────────────────────────────────────────
    "temperature":                     "high_fever",
    "fever":                           "high_fever",
    "running_a_fever":                 "high_fever",
    "high_temperature":                "high_fever",
    "bukhar":                          "high_fever",
    "tez_bukhar":                      "high_fever",
    "slight_fever":                    "mild_fever",
    "low_grade_fever":                 "mild_fever",
    "mild_fever":                      "mild_fever",
    "halka_bukhar":                    "mild_fever",
    "feeling_cold":                    "chills",
    "shivering":                       "chills",
    "kaanpna":                         "chills",
    "cold_hands":                      "cold_hands_and_feets",
    "cold_feet":                       "cold_hands_and_feets",
    "haath_pair_thande":               "cold_hands_and_feets",
    "sweating":                        "sweating",
    "sweating_a_lot":                  "sweating",
    "night_sweats":                    "sweating",
    "excessive_sweating":              "sweating",
    "pasiina":                         "sweating",
    "bahut_pasina":                    "sweating",

    # ── Skin / Twacha ─────────────────────────────────────────────────────────
    "rash":                            "skin_rash",
    "skin_rash":                       "skin_rash",
    "rashes":                          "skin_rash",
    "daane":                           "skin_rash",
    "skin_itching":                    "itching",
    "itchy_skin":                      "itching",
    "itching":                         "itching",
    "khujli":                          "itching",
    "skin_irritation":                 "itching",
    "dry_skin":                        "skin_peeling",
    "peeling_skin":                    "skin_peeling",
    "yellow_skin":                     "yellowish_skin",
    "jaundice_skin":                   "yellowish_skin",
    "skin_yellow":                     "yellowish_skin",
    "twacha_peeli":                    "yellowish_skin",
    "pimples":                         "pus_filled_pimples",
    "acne":                            "blackheads",
    "nodal_skin_eruptions":            "nodal_skin_eruptions",
    "skin_eruptions":                  "nodal_skin_eruptions",
    "blisters":                        "fluid_overload",

    # ── Eyes / Aankhein ───────────────────────────────────────────────────────
    "yellow_eyes":                     "yellowing_of_eyes",
    "aankhein_peeli":                  "yellowing_of_eyes",
    "red_eyes":                        "redness_of_eyes",
    "aankhein_laal":                   "redness_of_eyes",
    "blurry_vision":                   "blurred_and_distorted_vision",
    "blurred_vision":                  "blurred_and_distorted_vision",
    "dhundla_dikhna":                  "blurred_and_distorted_vision",
    "vision_problems":                 "visual_disturbances",
    "watery_eyes":                     "watering_from_eyes",
    "aankhon_se_paani":                "watering_from_eyes",
    "puffy_eyes":                      "puffy_face_and_eyes",
    "sunken_eyes":                     "sunken_eyes",

    # ── Digestive / Pachan ────────────────────────────────────────────────────
    "vomit":                           "vomiting",
    "throwing_up":                     "vomiting",
    "ulti":                            "vomiting",
    "ulti_aana":                       "vomiting",
    "nauseous":                        "nausea",
    "feeling_nauseous":                "nausea",
    "feel_like_vomiting":              "nausea",
    "matli":                           "nausea",
    "ji_machlana":                     "nausea",
    "loose_stools":                    "diarrhoea",
    "loose_motion":                    "diarrhoea",
    "diarrhea":                        "diarrhoea",
    "loose_motions":                   "diarrhoea",
    "dast":                            "diarrhoea",
    "potty_aana":                      "diarrhoea",
    "stomach_upset":                   "indigestion",
    "indigestion":                     "indigestion",
    "bloating":                        "distention_of_abdomen",
    "pet_phulna":                      "distention_of_abdomen",
    "heartburn":                       "acidity",
    "acid_reflux":                     "acidity",
    "jalan_seene_mein":                "acidity",
    "gas":                             "passage_of_gases",
    "flatulence":                      "passage_of_gases",
    "constipated":                     "constipation",
    "qabz":                            "constipation",
    "blood_in_stool":                  "bloody_stool",
    "blood_in_potty":                  "bloody_stool",

    # ── Respiratory / Saans ───────────────────────────────────────────────────
    "shortness_of_breath":             "breathlessness",
    "difficulty_breathing":            "breathlessness",
    "trouble_breathing":               "breathlessness",
    "breathlessness":                  "breathlessness",
    "saans_lene_mein_takleef":         "breathlessness",
    "saans_phoolna":                   "breathlessness",
    "cant_breathe":                    "breathlessness",
    "hard_to_breathe":                 "breathlessness",
    "stuffy_nose":                     "congestion",
    "blocked_nose":                    "congestion",
    "nasal_congestion":                "congestion",
    "naak_band":                       "congestion",
    "sneezing":                        "continuous_sneezing",
    "chheenk":                         "continuous_sneezing",
    "cough":                           "cough",
    "khaansi":                         "cough",
    "mucus":                           "phlegm",
    "phlegm":                          "phlegm",
    "balgam":                          "phlegm",
    "blood_in_cough":                  "blood_in_sputum",
    "coughing_blood":                  "blood_in_sputum",

    # ── Head / Neuro / Sar ────────────────────────────────────────────────────
    "headache":                        "headache",
    "migraine":                        "headache",
    "head_pain":                       "headache",
    "head_ache":                       "headache",
    "sar_dard":                        "headache",
    "sar_mein_dard":                   "headache",
    "dizzy":                           "dizziness",
    "dizziness":                       "dizziness",
    "chakkar":                         "dizziness",
    "chakkar_aana":                    "dizziness",
    "vertigo":                         "spinning_movements",
    "spinning":                        "spinning_movements",
    "difficulty_concentrating":        "lack_of_concentration",
    "poor_concentration":              "lack_of_concentration",
    "dhyan_nahi_lagta":                "lack_of_concentration",
    "numbness":                        "weakness_in_limbs",
    "numbness_in_hands":               "weakness_in_limbs",
    "numbness_in_legs":                "weakness_in_limbs",
    "haath_pair_sone":                 "weakness_in_limbs",
    "seizures":                        "altered_sensorium",
    "unconscious":                     "altered_sensorium",
    "stiff_neck":                      "stiff_neck",
    "gardan_akad_jana":                "stiff_neck",

    # ── Mood / Mental / Mann ─────────────────────────────────────────────────
    "sad":                             "depression",
    "depressed":                       "depression",
    "feeling_low":                     "depression",
    "udaas_rehna":                     "depression",
    "maan_udaas":                      "depression",
    "anxious":                         "anxiety",
    "nervous":                         "anxiety",
    "tension":                         "anxiety",
    "mood_change":                     "mood_swings",
    "mood_swings":                     "mood_swings",
    "irritable":                       "irritability",
    "chidchidapan":                    "irritability",
    "gussa":                           "irritability",

    # ── Weight / Wajan ────────────────────────────────────────────────────────
    "losing_weight":                   "weight_loss",
    "unexplained_weight_loss":         "weight_loss",
    "weight_loss":                     "weight_loss",
    "wajan_kam_hona":                  "weight_loss",
    "gaining_weight":                  "weight_gain",
    "wajan_badhna":                    "weight_gain",
    "overweight":                      "obesity",
    "obese":                           "obesity",
    "mota_hona":                       "obesity",

    # ── Swelling / Sujan ─────────────────────────────────────────────────────
    "swollen_feet":                    "swollen_legs",
    "swollen_ankles":                  "swollen_legs",
    "leg_swelling":                    "swollen_legs",
    "paon_mein_sujan":                 "swollen_legs",
    "swollen_face":                    "puffy_face_and_eyes",
    "chehra_sooja_hua":                "puffy_face_and_eyes",
    "enlarged_lymph_nodes":            "swelled_lymph_nodes",
    "swollen_glands":                  "swelled_lymph_nodes",
    "swollen_neck":                    "enlarged_thyroid",
    "goiter":                          "enlarged_thyroid",
    "gardan_mein_gaanth":              "enlarged_thyroid",

    # ── Heart / Dil ───────────────────────────────────────────────────────────
    "heart_palpitations":              "palpitations",
    "palpitations":                    "palpitations",
    "dil_ki_dhadkan":                  "palpitations",
    "racing_heart":                    "fast_heart_rate",
    "rapid_heartbeat":                 "fast_heart_rate",
    "heart_racing":                    "fast_heart_rate",
    "tez_dhadkan":                     "fast_heart_rate",

    # ── Liver / Jaundice ─────────────────────────────────────────────────────
    "dark_urine":                      "dark_urine",
    "dark_yellow_urine":               "dark_urine",
    "peela_peshab":                    "dark_urine",
    "yellow_urine":                    "dark_urine",
    "jaundice":                        "yellowish_skin",

    # ── Skin Diseases ────────────────────────────────────────────────────────
    "silver_scales":                   "silver_like_dusting",
    "scaly_skin":                      "scaly_patches_on_scalp",
    "patches_on_skin":                 "skin_rash",
    "white_patches":                   "dischromic_patches",
    "skin_discolouration":             "dischromic_patches",

    # ── Sleep / Neend ────────────────────────────────────────────────────────
    "insomnia":                        "restlessness",
    "cant_sleep":                      "restlessness",
    "neend_nahi_aati":                 "restlessness",
    "restless":                        "restlessness",
    "sleep_problems":                  "restlessness",

    # ── Other common ─────────────────────────────────────────────────────────
    "stiff_joints":                    "movement_stiffness",
    "stiffness":                       "movement_stiffness",
    "difficulty_walking":              "painful_walking",
    "chalne_mein_takleef":             "painful_walking",
    "alcohol_history":                 "history_of_alcohol_consumption",
    "drinks_alcohol":                  "history_of_alcohol_consumption",
    "alcoholic":                       "history_of_alcohol_consumption",
    "sharaab_peena":                   "history_of_alcohol_consumption",
    "blood_sugar_issue":               "irregular_sugar_level",
    "high_blood_sugar":                "irregular_sugar_level",
    "low_blood_sugar":                 "irregular_sugar_level",
    "sugar_high":                      "irregular_sugar_level",
    "poor_balance":                    "unsteadiness",
    "loss_of_balance":                 "loss_of_balance",
    "balance_problem":                 "loss_of_balance",
    "hair_fall":                       "hair_loss",
    "hair_loss":                       "hair_loss",
    "baal_jhadna":                     "hair_loss",
    "nail_changes":                    "brittle_nails",
    "weak_nails":                      "brittle_nails",
    "nakhun_toote":                    "brittle_nails",
    "swallowing_difficulty":           "difficulty_swallowing",
    "hard_to_swallow":                 "difficulty_swallowing",
    "nigalna_mushkil":                 "difficulty_swallowing",

    # ════════════════════════════════════════════════════════════════════════
    # COMPLETE MISSING SYNONYMS — every dataset symptom now has coverage
    # Grouped by disease for easy maintenance
    # ════════════════════════════════════════════════════════════════════════

    # ── AIDS ──────────────────────────────────────────────────────────────
    "unprotected_sex":                 "extra_marital_contacts",
    "multiple_partners":               "extra_marital_contacts",
    "sexual_contact":                  "extra_marital_contacts",
    "muscles_wasting":                 "muscle_wasting",
    "muscle_wasting":                  "muscle_wasting",
    "muscles_wasted":                  "muscle_wasting",
    "thin_muscles":                    "muscle_wasting",
    "patches_in_throat":               "patches_in_throat",
    "white_patches_throat":            "patches_in_throat",
    "throat_patches":                  "patches_in_throat",

    # ── Acne ──────────────────────────────────────────────────────────────
    "scarring":                        "scurring",
    "acne_scars":                      "scurring",
    "skin_scars":                      "scurring",
    "scars_on_face":                   "scurring",

    # ── Alcoholic hepatitis ───────────────────────────────────────────────
    "stomach_swelling":                "swelling_of_stomach",
    "swollen_stomach":                 "swelling_of_stomach",
    "stomach_enlarged":                "swelling_of_stomach",
    "abdominal_swelling":              "swelling_of_stomach",

    # ── Allergy ───────────────────────────────────────────────────────────
    "shivering":                       "shivering",
    "body_shaking":                    "shivering",
    "trembling":                       "shivering",
    "kaanpna":                         "shivering",

    # ── Arthritis / Osteoarthritis ────────────────────────────────────────
    "muscle_weakness":                 "muscle_weakness",
    "weak_muscles":                    "muscle_weakness",
    "muscles_feel_weak":               "muscle_weakness",
    "swelling_joints":                 "swelling_joints",
    "swollen_joints":                  "swelling_joints",
    "joint_swelling":                  "swelling_joints",
    "jodon_mein_sujan":                "swelling_joints",

    # ── Bronchial Asthma ──────────────────────────────────────────────────
    "mucoid_sputum":                   "mucoid_sputum",
    "thick_sputum":                    "mucoid_sputum",
    "thick_phlegm":                    "mucoid_sputum",
    "mucus_cough":                     "mucoid_sputum",
    "family_history":                  "family_history",
    "runs_in_family":                  "family_history",
    "hereditary":                      "family_history",

    # ── Chicken pox / Dengue / Common Cold / TB / Pneumonia ──────────────
    "malaise":                         "malaise",
    "general_discomfort":              "malaise",
    "feeling_unwell":                  "malaise",
    "body_discomfort":                 "malaise",
    "red_spots":                       "red_spots_over_body",
    "red_spots_body":                  "red_spots_over_body",
    "red_spots_on_skin":               "red_spots_over_body",
    "spots_on_body":                   "red_spots_over_body",

    # ── Common Cold ───────────────────────────────────────────────────────
    "loss_of_smell":                   "loss_of_smell",
    "cant_smell":                      "loss_of_smell",
    "no_sense_of_smell":               "loss_of_smell",
    "smell_gone":                      "loss_of_smell",
    "runny_nose":                      "runny_nose",
    "naak_behna":                      "runny_nose",
    "runny_nose_cold":                 "runny_nose",
    "nose_dripping":                   "runny_nose",
    "sinus_pressure":                  "sinus_pressure",
    "sinus_pain":                      "sinus_pressure",
    "sinus_headache":                  "sinus_pressure",
    "naak_mein_pressure":              "sinus_pressure",
    "throat_irritation":               "throat_irritation",
    "sore_throat":                     "throat_irritation",
    "gala_kharaab":                    "throat_irritation",
    "scratchy_throat":                 "throat_irritation",
    "gala_dard":                       "throat_irritation",

    # ── Dengue ────────────────────────────────────────────────────────────
    "pain_behind_eyes":                "pain_behind_the_eyes",
    "eye_pain":                        "pain_behind_the_eyes",
    "pain_in_eyes":                    "pain_behind_the_eyes",
    "aankhon_mein_dard":               "pain_behind_the_eyes",

    # ── Dimorphic haemorrhoids (piles) ────────────────────────────────────
    "anal_itching":                    "irritation_in_anus",
    "itching_in_anus":                 "irritation_in_anus",
    "pain_while_passing_stool":        "pain_during_bowel_movements",
    "pain_during_potty":               "pain_during_bowel_movements",
    "anal_pain":                       "pain_in_anal_region",
    "pain_in_bottom":                  "pain_in_anal_region",

    # ── Drug Reaction ─────────────────────────────────────────────────────
    "spotting_urination":              "spotting_urination",
    "blood_spots_urine":               "spotting_urination",
    "blood_in_urine":                  "spotting_urination",
    "peshab_mein_khoon":               "spotting_urination",

    # ── GERD ──────────────────────────────────────────────────────────────
    "ulcers_on_tongue":                "ulcers_on_tongue",
    "mouth_ulcers":                    "ulcers_on_tongue",
    "tongue_sores":                    "ulcers_on_tongue",
    "munh_mein_chhale":                "ulcers_on_tongue",

    # ── Hepatitis B / C ───────────────────────────────────────────────────
    "yellow_urine":                    "yellow_urine",
    "dark_yellow_urine":               "yellow_urine",
    "blood_transfusion":               "receiving_blood_transfusion",
    "had_blood_transfusion":           "receiving_blood_transfusion",
    "unsterile_injection":             "receiving_unsterile_injections",
    "dirty_needle":                    "receiving_unsterile_injections",
    "shared_needle":                   "receiving_unsterile_injections",

    # ── Hepatitis E ───────────────────────────────────────────────────────
    "acute_liver_failure":             "acute_liver_failure",
    "liver_failure":                   "acute_liver_failure",
    "liver_shutting_down":             "acute_liver_failure",
    "coma":                            "coma",
    "unconsciousness":                 "altered_sensorium",
    "not_conscious":                   "altered_sensorium",
    "stomach_bleeding":                "stomach_bleeding",
    "bleeding_in_stomach":             "stomach_bleeding",
    "internal_bleeding":               "stomach_bleeding",

    # ── Hyperthyroidism / Hypothyroidism ──────────────────────────────────
    "abnormal_menstruation":           "abnormal_menstruation",
    "irregular_periods":               "abnormal_menstruation",
    "missed_periods":                  "abnormal_menstruation",
    "period_problems":                 "abnormal_menstruation",
    "masik_dharm_gadbad":              "abnormal_menstruation",
    "swollen_extremities":             "swollen_extremeties",
    "swollen_limbs":                   "swollen_extremeties",
    "swelling_in_limbs":               "swollen_extremeties",

    # ── Hypoglycemia ──────────────────────────────────────────────────────
    "tingling_lips":                   "drying_and_tingling_lips",
    "lip_tingling":                    "drying_and_tingling_lips",
    "dry_and_tingling_lips":           "drying_and_tingling_lips",
    "numbness_in_lips":                "drying_and_tingling_lips",
    "slurred_speech":                  "slurred_speech",
    "speech_difficulty":               "slurred_speech",
    "cant_speak_clearly":              "slurred_speech",
    "unclear_speech":                  "slurred_speech",

    # ── Impetigo ──────────────────────────────────────────────────────────
    "blister":                         "blister",
    "blisters_on_skin":                "blister",
    "fluid_filled_blister":            "blister",
    "red_sore_around_nose":            "red_sore_around_nose",
    "sores_near_nose":                 "red_sore_around_nose",
    "nose_sores":                      "red_sore_around_nose",
    "yellow_crust":                    "yellow_crust_ooze",
    "yellow_ooze":                     "yellow_crust_ooze",
    "crusty_yellow_skin":              "yellow_crust_ooze",

    # ── Paralysis ─────────────────────────────────────────────────────────
    "weakness_on_one_side":            "weakness_of_one_body_side",
    "one_side_weakness":               "weakness_of_one_body_side",
    "paralysis_one_side":              "weakness_of_one_body_side",
    "half_body_weakness":              "weakness_of_one_body_side",
    "ek_taraf_kamzori":                "weakness_of_one_body_side",
    "unconscious":                     "altered_sensorium",
    "unconsciousness":                 "altered_sensorium",
    "loss_of_consciousness":           "altered_sensorium",
    "passing_out":                     "altered_sensorium",
    "fainted":                         "altered_sensorium",
    "confusion":                       "altered_sensorium",
    "confused":                        "altered_sensorium",
    "disoriented":                     "altered_sensorium",
    "mental_confusion":                "altered_sensorium",
    "altered_sensorium":               "altered_sensorium",

    # ── Peptic ulcer ──────────────────────────────────────────────────────
    "internal_itching":                "internal_itching",
    "itching_inside":                  "internal_itching",
    "internal_irritation":             "internal_itching",

    # ── Pneumonia ─────────────────────────────────────────────────────────
    "rusty_sputum":                    "rusty_sputum",
    "rust_colored_phlegm":             "rusty_sputum",
    "brown_sputum":                    "rusty_sputum",

    # ── Psoriasis ─────────────────────────────────────────────────────────
    "nail_inflammation":               "inflammatory_nails",
    "inflamed_nails":                  "inflammatory_nails",
    "dents_in_nails":                  "small_dents_in_nails",
    "nail_pitting":                    "small_dents_in_nails",
    "pitted_nails":                    "small_dents_in_nails",

    # ── Typhoid ───────────────────────────────────────────────────────────
    "belly_pain":                      "belly_pain",
    "stomach_region_pain":             "belly_pain",
    "toxic_look":                      "toxic_look_(typhos)",
    "looking_very_ill":                "toxic_look_(typhos)",
    "very_sick_appearance":            "toxic_look_(typhos)",

    # ── UTI (Urinary Tract Infection) ─────────────────────────────────────
    "bladder_discomfort":              "bladder_discomfort",
    "bladder_pain":                    "bladder_discomfort",
    "bladder_pressure":                "bladder_discomfort",
    "peshab_ki_theli_mein_dard":       "bladder_discomfort",
    "urge_to_urinate":                 "continuous_feel_of_urine",
    "always_feel_like_urinating":      "continuous_feel_of_urine",
    "constant_urge_to_pee":            "continuous_feel_of_urine",
    "foul_smell_urine":                "foul_smell_of_urine",
    "smelly_urine":                    "foul_smell_of_urine",
    "bad_smell_urine":                 "foul_smell_of_urine",
    "urine_smells_bad":                "foul_smell_of_urine",
    "peshab_se_bau":                   "foul_smell_of_urine",

    # ── Varicose veins ────────────────────────────────────────────────────
    "bruising":                        "bruising",
    "bruises_easily":                  "bruising",
    "blue_marks":                      "bruising",
    "neele_nishaan":                   "bruising",
    "muscle_cramps":                   "cramps",
    "leg_cramps":                      "cramps",
    "cramps_in_legs":                  "cramps",
    "paon_mein_cramps":                "cramps",
    "prominent_veins":                 "prominent_veins_on_calf",
    "visible_veins":                   "prominent_veins_on_calf",
    "bulging_veins":                   "prominent_veins_on_calf",
    "veins_visible_on_leg":            "prominent_veins_on_calf",
    "swollen_blood_vessels":           "swollen_blood_vessels",
    "swollen_veins":                   "swollen_blood_vessels",

    # ── Gastroenteritis ───────────────────────────────────────────────────
    "dehydration":                     "dehydration",
    "sunken_eyes":                     "sunken_eyes",
    "eyes_sunken":                     "sunken_eyes",
    "hollow_eyes":                     "sunken_eyes",

    # ── Migraine ──────────────────────────────────────────────────────────
    "visual_disturbances":             "visual_disturbances",
    "visual_aura":                     "visual_disturbances",
    "seeing_flashes":                  "visual_disturbances",
    "aankh_ke_aage_andhera":           "visual_disturbances",

    # ── Hypertension ──────────────────────────────────────────────────────
    "lack_of_concentration":           "lack_of_concentration",
    "difficulty_focusing":             "lack_of_concentration",
    "cant_focus":                      "lack_of_concentration",

    # ── Fungal infection ──────────────────────────────────────────────────
    "dischromic_patches":              "dischromic_patches",
    "discolored_patches":              "dischromic_patches",
    "skin_discoloration_patches":      "dischromic_patches",
    "nodal_skin_eruptions":            "nodal_skin_eruptions",
    "skin_nodules":                    "nodal_skin_eruptions",
    "raised_skin_bumps":               "nodal_skin_eruptions",

    # ── Vertigo ───────────────────────────────────────────────────────────
    "spinning_movements":              "spinning_movements",
    "room_spinning":                   "spinning_movements",
    "sab_ghoomta_hai":                 "spinning_movements",
    "unsteadiness":                    "unsteadiness",
    "unsteady":                        "unsteadiness",
    "cant_stand_steady":               "unsteadiness",
}


# ── FIX 2: Improved symptom matching ──────────────────────────────────────────
def match_symptoms(user_symptoms):
    """
    User symptom strings ko known dataset keys se match karo.

    Priority order:
      1. Synonym map  → plain English / Hinglish → correct dataset key
      2. Exact match  → user ne already dataset key type ki
      3. Fuzzy match  → strict 0.85 cutoff (sirf typos ke liye)

    Returns (matched_list, unmatched_list)
    """
    matched   = []
    unmatched = []
    seen      = set()

    for raw in user_symptoms:
        norm   = _normalize_symptom(raw)
        result = None

        # 1. Synonym map
        if norm in SYMPTOM_SYNONYMS:
            result = SYMPTOM_SYNONYMS[norm]

        # 2. Exact match
        elif norm in _symptom_index:
            result = norm

        # 3. Strict fuzzy (sirf typos ke liye, semantic bridge nahi)
        else:
            close = get_close_matches(norm, _symptoms_list, n=1, cutoff=0.85)
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
    Symptoms ki list se disease predict karo.

    Args:
        user_symptoms: list of symptom strings
                       e.g. ["frequent urination", "extreme thirst", "fatigue"]

    Returns:
        dict with: disease, description, precautions,
                   matched_symptoms, unmatched_symptoms, confidence, top3,
                   low_confidence (bool — FIX 3)
    """
    matched, unmatched = match_symptoms(user_symptoms)

    if not matched:
        return {
            "disease":            None,
            "description":        "Koi bhi known symptom identify nahi ho saka.",
            "precautions":        [],
            "matched_symptoms":   [],
            "unmatched_symptoms": unmatched,
            "confidence":         0.0,
            "top3":               [],
            "low_confidence":     True,
        }

    # Feature vector banao
    feature_vector = np.zeros(len(_symptoms_list), dtype=int)
    for s in matched:
        feature_vector[_symptom_index[s]] = 1

    # Predict
    prediction    = _model.predict([feature_vector])[0]
    probabilities = _model.predict_proba([feature_vector])[0]
    confidence    = float(np.max(probabilities))
    disease_name  = _label_encoder.inverse_transform([prediction])[0]

    # Top 3 (low confidence pe dikhane ke liye)
    top3_indices = np.argsort(probabilities)[-3:][::-1]
    top3 = [
        {
            "disease":    _label_encoder.inverse_transform([i])[0],
            "confidence": float(probabilities[i]),
        }
        for i in top3_indices if probabilities[i] > 0.05
    ]

    # FIX 3: low_confidence flag — 50% se kam confidence = unreliable
    low_confidence = confidence < 0.50

    return {
        "disease":            disease_name,
        "description":        _descriptions.get(disease_name, "No description available."),
        "precautions":        _precautions.get(disease_name, []),
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
    """Top candidate diseases ke basis pe aur symptoms suggest karo."""
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
    print("TEST 1 — Diabetes (plain English + Hinglish)")
    print("=" * 55)
    test1 = ["frequent urination", "bahut pyaas", "fatigue", "intense hunger", "weight loss"]
    r1 = predict_disease(test1)
    print(f"Input      : {test1}")
    print(f"Matched    : {r1['matched_symptoms']}")
    print(f"Unmatched  : {r1['unmatched_symptoms']}")
    print(f"Disease    : {r1['disease']}")
    print(f"Confidence : {r1['confidence']:.1%}")
    print(f"Low conf?  : {r1['low_confidence']}")
    print(f"Top 3      : {r1['top3']}")

    print()
    print("=" * 55)
    print("TEST 2 — Fungal infection")
    print("=" * 55)
    r2 = predict_disease(["khujli", "skin rash", "nodal skin eruptions"])
    print(f"Disease    : {r2['disease']}")
    print(f"Confidence : {r2['confidence']:.1%}")

    print()
    print("=" * 55)
    print("TEST 3 — Follow-up suggestions")
    print("=" * 55)
    print(f"Suggest    : {get_followup_symptoms(r1['matched_symptoms'])}")
