"""
train_model.py — Train a symptom-based disease prediction model.

Usage:
    python prediction_model/train_model.py

This script:
1. Loads dataset.csv and cleans symptom names
2. Creates binary feature vectors for each symptom
3. Trains a Random Forest classifier
4. Evaluates accuracy on a held-out test set
5. Saves the trained model and metadata to prediction_model/saved_model/
"""

import os
import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import accuracy_score, classification_report
import joblib

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "data", "dataset.csv")
SAVE_DIR = os.path.join(BASE_DIR, "saved_model")


# ── BUG FIX #1: Correct symptom normalization ─────────────────────────────────
# OLD (broken): str(val).strip().replace(" ", "")   ← removes ALL spaces first
#               then .lower().replace(" ", "_")      ← no spaces left to replace!
#
# This caused 3 symptoms with embedded spaces to be mangled:
#   "spotting_ urination"  → "spotting__urination"  (double underscore)
#   "foul_smell_of urine"  → "foul_smell_ofurine"   (merged words)
#   "dischromic _patches"  → "dischromic__patches"  (double underscore)
#
# NEW (fixed): single-pass normalization — strip, lowercase, collapse all
#              whitespace variants into a single underscore.
def normalize_symptom(val):
    """
    Normalize a raw symptom string from the CSV into a consistent key.

    Steps:
      1. Convert to string and strip leading/trailing whitespace
      2. Lowercase
      3. Replace hyphens with underscores
      4. Split on whitespace (handles spaces, tabs, multiple spaces)
         and rejoin with a single underscore
      5. Collapse any runs of multiple underscores into one
    """
    import re
    s = str(val).strip().lower().replace("-", "_")
    # join words on any whitespace with underscore
    s = "_".join(s.split())
    # collapse double (or more) underscores produced by stray spaces in CSV
    s = re.sub(r"_+", "_", s)
    return s


def load_and_clean_data(path):
    """Load dataset.csv and return (diseases, symptom_lists)."""
    df = pd.read_csv(path, header=None)

    diseases = []
    symptom_lists = []

    for _, row in df.iterrows():
        disease = str(row.iloc[0]).strip()
        if not disease or disease == "nan":
            continue

        symptoms = []
        for val in row.iloc[1:]:
            # ── BUG FIX #1 applied here ───────────────────────────────────
            s = normalize_symptom(val)
            if s and s != "nan":
                symptoms.append(s)

        if symptoms:
            diseases.append(disease)
            symptom_lists.append(symptoms)

    return diseases, symptom_lists


def build_feature_matrix(diseases, symptom_lists):
    """Create binary feature matrix from symptom lists."""
    # Collect all unique symptoms
    all_symptoms = sorted(set(s for sl in symptom_lists for s in sl))
    print(f"📊 Total unique symptoms: {len(all_symptoms)}")
    print(f"📊 Total samples: {len(diseases)}")

    # Build binary matrix
    symptom_index = {s: i for i, s in enumerate(all_symptoms)}
    X = np.zeros((len(symptom_lists), len(all_symptoms)), dtype=int)

    for i, symptoms in enumerate(symptom_lists):
        for s in symptoms:
            if s in symptom_index:
                X[i, symptom_index[s]] = 1

    # ── BUG FIX #2: Normalize disease names before label encoding ─────────
    # Dataset has trailing spaces in some disease names e.g. "Diabetes " and
    # "Hypertension " which caused duplicate classes in the encoder.
    diseases_clean = [d.strip() for d in diseases]

    le = LabelEncoder()
    y = le.fit_transform(diseases_clean)

    print(f"📊 Total diseases: {len(le.classes_)}")
    return X, y, all_symptoms, le


def train_and_evaluate(X, y, le):
    """Train Voting Classifier (Random Forest + Decision Tree) and print evaluation metrics."""
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print(f"\n📊 Dataset explicitly divided into training and testing sets:")
    print(f"   - Training set: {X_train.shape[0]} samples")
    print(f"   - Testing set:  {X_test.shape[0]} samples")

    print("\n🔧 Training Ensemble Model (Random Forest + Decision Tree)...")

    rf_model = RandomForestClassifier(
        n_estimators=100,
        random_state=42,
        n_jobs=-1,
    )
    dt_model = DecisionTreeClassifier(random_state=42)

    model = VotingClassifier(
        estimators=[("rf", rf_model), ("dt", dt_model)],
        voting="soft",
    )

    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n✅ Test Accuracy: {accuracy * 100:.2f}%")
    print("\n📋 Classification Report:\n")
    print(classification_report(y_test, y_pred, target_names=le.classes_))

    return model


def save_artifacts(model, le, all_symptoms):
    """Save model, label encoder, and symptoms list."""
    os.makedirs(SAVE_DIR, exist_ok=True)

    model_path    = os.path.join(SAVE_DIR, "model.pkl")
    le_path       = os.path.join(SAVE_DIR, "label_encoder.pkl")
    symptoms_path = os.path.join(SAVE_DIR, "symptoms_list.pkl")

    joblib.dump(model, model_path)
    joblib.dump(le, le_path)
    joblib.dump(all_symptoms, symptoms_path)

    print(f"\n💾 Model saved to:          {model_path}")
    print(f"💾 Label encoder saved to:  {le_path}")
    print(f"💾 Symptoms list saved to:  {symptoms_path}")


def main():
    print("=" * 60)
    print("  HealSmart — Disease Prediction Model Training")
    print("=" * 60)

    # 1. Load data
    print(f"\n📂 Loading data from: {DATA_PATH}")
    diseases, symptom_lists = load_and_clean_data(DATA_PATH)

    # 2. Build features
    X, y, all_symptoms, le = build_feature_matrix(diseases, symptom_lists)

    # 3. Train & evaluate
    model = train_and_evaluate(X, y, le)

    # 4. Save
    save_artifacts(model, le, all_symptoms)

    print("\n🎉 Training complete!")


if __name__ == "__main__":
    main()