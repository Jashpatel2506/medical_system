"""
train_model.py — Train a symptom-based disease prediction model.

FIX SUMMARY (kya fix kiya):
  FIX 1: RandomForestClassifier + DecisionTreeClassifier mein class_weight="balanced" add kiya
          → Isse imbalanced dataset ka bias khatam hoga (most important fix)
  FIX 2: Symptom normalization consistent rakha (same as predict.py)
  FIX 3: Disease name strip() add kiya (trailing spaces se duplicate classes ban rahe the)

Usage:
    python prediction_model/train_model.py
"""

import os
import re
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "dataset.csv")
SAVE_DIR  = os.path.join(BASE_DIR, "saved_model")


# ── Symptom normalization (predict.py ke saath EXACTLY same hona chahiye) ──────
def normalize_symptom(val):
    """
    Raw CSV value ko consistent dataset key mein convert karo.
    IMPORTANT: yahi function predict.py mein bhi use hota hai — dono sync mein rahein.
    """
    s = str(val).strip().lower().replace("-", "_")
    s = "_".join(s.split())        # koi bhi whitespace → single underscore
    s = re.sub(r"_+", "_", s)     # double underscore collapse
    return s


def load_and_clean_data(path):
    """dataset.csv load karo aur (diseases, symptom_lists) return karo."""
    df = pd.read_csv(path, header=None)

    diseases      = []
    symptom_lists = []

    for _, row in df.iterrows():
        disease = str(row.iloc[0]).strip()
        if not disease or disease == "nan":
            continue

        symptoms = []
        for val in row.iloc[1:]:
            s = normalize_symptom(val)
            if s and s != "nan":
                symptoms.append(s)

        if symptoms:
            diseases.append(disease)
            symptom_lists.append(symptoms)

    return diseases, symptom_lists


def build_feature_matrix(diseases, symptom_lists):
    """Binary feature matrix banao symptom lists se."""
    all_symptoms = sorted(set(s for sl in symptom_lists for s in sl))
    print(f"📊 Total unique symptoms : {len(all_symptoms)}")
    print(f"📊 Total samples         : {len(diseases)}")

    symptom_index = {s: i for i, s in enumerate(all_symptoms)}
    X = np.zeros((len(symptom_lists), len(all_symptoms)), dtype=int)

    for i, symptoms in enumerate(symptom_lists):
        for s in symptoms:
            if s in symptom_index:
                X[i, symptom_index[s]] = 1

    # FIX 2: Disease name strip karo — trailing spaces se duplicates bante the
    diseases_clean = [d.strip() for d in diseases]

    le = LabelEncoder()
    y  = le.fit_transform(diseases_clean)

    print(f"📊 Total diseases        : {len(le.classes_)}")
    return X, y, all_symptoms, le


def train_and_evaluate(X, y, le):
    """
    Voting Classifier train karo aur evaluate karo.

    ★ FIX 1 (MOST IMPORTANT): class_weight='balanced' add kiya dono models mein
      Problem tha: Dataset imbalanced hai (kuch diseases ke zyada samples, kuch ke kam)
      → Bina class_weight ke model common diseases ko zyada predict karta tha
      → class_weight='balanced' se har disease ko equal importance milti hai
    """
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\n📊 Training set  : {X_train.shape[0]} samples")
    print(f"📊 Testing set   : {X_test.shape[0]} samples")
    print("\n🔧 Training Ensemble Model (Random Forest + Decision Tree)...")

    # ★ FIX 1: class_weight="balanced" — ZAROOR RAKHO
    rf_model = RandomForestClassifier(
        n_estimators=200,          # 100 se badhakar 200 kiya — better accuracy
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",   # ← FIX: imbalanced dataset handle karega
        min_samples_leaf=2,        # overfitting reduce karega
    )

    dt_model = DecisionTreeClassifier(
        random_state=42,
        class_weight="balanced",   # ← FIX: yahan bhi zaroor hai
        min_samples_leaf=2,
    )

    model = VotingClassifier(
        estimators=[("rf", rf_model), ("dt", dt_model)],
        voting="soft",
    )

    model.fit(X_train, y_train)

    # Evaluation
    y_pred   = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n✅ Test Accuracy: {accuracy * 100:.2f}%")
    print("\n📋 Classification Report:\n")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    return model


def save_artifacts(model, le, all_symptoms):
    """Model, label encoder, aur symptoms list save karo."""
    os.makedirs(SAVE_DIR, exist_ok=True)

    model_path    = os.path.join(SAVE_DIR, "model.pkl")
    le_path       = os.path.join(SAVE_DIR, "label_encoder.pkl")
    symptoms_path = os.path.join(SAVE_DIR, "symptoms_list.pkl")

    joblib.dump(model,        model_path)
    joblib.dump(le,           le_path)
    joblib.dump(all_symptoms, symptoms_path)

    print(f"\n💾 Model saved          : {model_path}")
    print(f"💾 Label encoder saved  : {le_path}")
    print(f"💾 Symptoms list saved  : {symptoms_path}")


def main():
    print("=" * 60)
    print("  HealSmart — Disease Prediction Model Training")
    print("=" * 60)

    print(f"\n📂 Loading data from: {DATA_PATH}")
    diseases, symptom_lists = load_and_clean_data(DATA_PATH)

    X, y, all_symptoms, le = build_feature_matrix(diseases, symptom_lists)

    model = train_and_evaluate(X, y, le)

    save_artifacts(model, le, all_symptoms)

    print("\n🎉 Training complete! Ab naya model.pkl use karo.")


if __name__ == "__main__":
    main()