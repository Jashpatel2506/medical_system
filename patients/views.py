from django.shortcuts import render, redirect
from django.http import JsonResponse
from patients.models import Patient
from users.models import User
import json
import os
import logging

logger = logging.getLogger(__name__)

def patient_page(request):

    if request.session.get("role") != "Patient":
        return redirect("login")

    user = User.objects.get(id=request.session["user_id"])
    patient = Patient.objects.filter(user=user).first()

    if request.method == "POST":
        full_name = request.POST.get("full_name", "").strip()
        if full_name:
            user.full_name = full_name
            user.save()

        if not patient:
            patient = Patient(user=user)

        patient.blood_group = request.POST.get("blood_group", "")
        patient.emergency_contact = request.POST.get("emergency_contact", "")

        height = request.POST.get("height_cm", "").strip()
        weight = request.POST.get("weight_kg", "").strip()
        age    = request.POST.get("age", "").strip()

        patient.height_cm = int(height) if height else None
        patient.weight_kg = int(weight) if weight else None
        patient.age       = int(age)    if age    else None

        try:
            patient.save()
            print("✅ Saved successfully!")
        except Exception as e:
            logger.error("❌ Save failed:", e)

        return redirect("patient_dashboard")

    return render(request, "patient/patient.html", {
        "patient": patient,
        "user": user,
        "saved": False,
        "notifications_count": 0
    })

# ==================== PATIENT DASHBOARD ====================

from django.shortcuts import render, redirect
from users.models import User
from patients.models import Patient
from doctors.models import Doctor
from appointments.models import Appointment


def patient_dashboard(request):

    if request.session.get("role") != "Patient":
        return redirect("login")

    try:
        user = User.objects.get(id=request.session["user_id"])
        patient = Patient.objects.filter(user=user).first()

        doctors = Doctor.objects.select_related("user").all()

        # Search filters
        search_name = request.GET.get('name', '').strip()
        search_city = request.GET.get('city', '').strip()
        search_spec = request.GET.get('specialization', '').strip()
        search_disease = request.GET.get('disease', '').strip()

        if search_name:
            doctors = doctors.filter(user__full_name__icontains=search_name)
        if search_city:
            from django.db.models import Q
            doctors = doctors.filter(Q(clinic_name__icontains=search_city) | Q(user__address__icontains=search_city))
        if search_spec:
            doctors = doctors.filter(specialization__icontains=search_spec)
        #if search_disease:
            #from django.db.models import Q
            #doctors = doctors.filter(
                #Q(specialization__icontains=search_disease) | 
                #Q(qualifications__icontains=search_disease)
            #)

        # Apply limit after all filters
        doctors = doctors[:6]

        appointments = Appointment.objects.filter(patient=patient, status='Booked').select_related("doctor__user")
        pending_appointments = Appointment.objects.filter(patient=patient, status='Pending').select_related("doctor__user")
        cancelled_appointments = Appointment.objects.filter(patient=patient, status='Cancelled').select_related("doctor__user")
        completed_appointments = Appointment.objects.filter(patient=patient, status='Completed').select_related("doctor__user")

        upcoming_count = appointments.count()
        pending_count = pending_appointments.count()
        cancelled_count = cancelled_appointments.count()
        completed_count = completed_appointments.count()

        for appt in cancelled_appointments:
            if "\n\n[CANCEL_REASON]" in appt.reason_for_visit:
                parts = appt.reason_for_visit.split("\n\n[CANCEL_REASON]")
                appt.display_reason = parts[0]
                appt.cancel_reason = parts[1]
            else:
                appt.display_reason = appt.reason_for_visit
                appt.cancel_reason = "No reason provided."

        context = {
            "user": user,
            "patient": patient,
            "doctors": doctors,
            "appointments": appointments,
            "pending_appointments": pending_appointments,
            "cancelled_appointments": cancelled_appointments,
            "completed_appointments": completed_appointments,
            "upcoming_count": upcoming_count,
            "pending_count": pending_count,
            "cancelled_count": cancelled_count,
            "completed_count": completed_count,
            "notifications_count": 0
        }

        return render(request, "patient/patient_dashboard.html", context)

    except User.DoesNotExist:
        return redirect("login")

def all_doctors(request):
    if request.session.get("role") != "Patient":
        return redirect("login")

    try:
        user = User.objects.get(id=request.session["user_id"])
        patient = Patient.objects.filter(user=user).first()
        
        doctors = Doctor.objects.select_related("user").all()

        # Search filters
        search_name = request.GET.get('name', '').strip()
        search_city = request.GET.get('city', '').strip()
        search_spec = request.GET.get('specialization', '').strip()

        if search_name:
            doctors = doctors.filter(user__full_name__icontains=search_name)
        if search_city:
            from django.db.models import Q
            doctors = doctors.filter(Q(clinic_name__icontains=search_city) | Q(user__address__icontains=search_city))
        if search_spec:
            doctors = doctors.filter(specialization__icontains=search_spec)

        context = {
            "user": user,
            "patient": patient,
            "doctors": doctors,
            "notifications_count": 0
        }
        return render(request, "patient/all_doctors.html", context)

    except User.DoesNotExist:
        return redirect("login")
# ==================== APPOINTMENT VIEWS ====================

from django.shortcuts import render, redirect
from doctors.models import Doctor
from patients.models import Patient
from appointments.models import Appointment

import json
from datetime import datetime
from django.http import JsonResponse

def book_appointment(request):

    if request.method == "POST":
        try:
            data = json.loads(request.body)

            doctor_id = data.get("doctor_id")
            date = data.get("date")
            time_str = data.get("time")
            reason = data.get("reason")

            print("Doctor ID:", doctor_id)
            print("Date:", date)
            print("Time:", time_str)
            print("Reason:", reason)

            # convert "09:00 AM" → time object
            appointment_time = datetime.strptime(time_str, "%I:%M %p").time()

            patient = Patient.objects.get(user_id=request.session["user_id"])
            doctor = Doctor.objects.get(id=doctor_id)

            if Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date,
                appointment_time=appointment_time
            ).exists():
                return JsonResponse({"success": False, "error": "Slot already booked"})

            Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                appointment_date=date,
                appointment_time=appointment_time,
                reason_for_visit=reason,
                status='Pending'   # ✅ always pending when patient books

                
            )

            return JsonResponse({"success": True})

        except Exception as e:
            print("ERROR:", e)
            return JsonResponse({"success": False})
# ==================== CHAT VIEWS ====================

def chat_view(request):
    """Patient chat interface"""
    
    # Check if user is logged in and is a patient
    if request.session.get("role") != "Patient":
        return redirect("login")
    
    try:
        user = User.objects.get(id=request.session["user_id"])
        patient = Patient.objects.filter(user=user).first()
        
        return render(request, 'patient/healsmart_professional_chat.html', {
            'user': user,
            'patient': patient,
            'notifications_count': 0
        })
    except User.DoesNotExist:
        return redirect("login")


def chat_api(request):
    """Handle chat messages via AJAX — multi-step symptom collection."""
    
    # Check if user is logged in
    if request.session.get("role") != "Patient":
        return JsonResponse({
            'success': False,
            'error': 'Please login to continue'
        }, status=401)
    
    if request.method == 'POST':
        try:
            # Parse JSON data from request
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            
            # Validate message
            if not user_message:
                return JsonResponse({
                    'success': False,
                    'error': 'Message cannot be empty'
                }, status=400)
            
            # Get user info for personalization
            user = User.objects.get(id=request.session["user_id"])
            patient = Patient.objects.filter(user=user).first()
            
            # Log the conversation (optional)
            logger.info(f"Patient {user.full_name} said: {user_message}")
            
            # Generate AI response (pass request for session access)
            bot_response = generate_response(user_message, request, patient)
            
            # Return response
            return JsonResponse({
                'success': True,
                'response': bot_response
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            }, status=400)
            
        except User.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'User not found'
            }, status=404)
            
        except Exception as e:
            logger.error(f"Chat API error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': 'Something went wrong. Please try again.'
            }, status=500)
    
    # If not POST request
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    }, status=405)


import re
import sys
from doctors.models import Doctor

# Add project root to path so prediction_model can be imported
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from prediction_model.predict import predict_disease, match_symptoms, get_followup_symptoms, _symptoms_list


# ── Disease → Specialization mapping ─────────────────────────────────────────
DISEASE_SPECIALIZATION_MAP = {
    # Infectious / Viral
    "Fungal infection":              ["Dermatology", "Dermatologist"],
    "Allergy":                       ["Allergy", "Immunology", "ENT"],
    "GERD":                          ["Gastroenterology", "Gastroenterologist"],
    "Chronic cholestasis":           ["Gastroenterology", "Hepatology"],
    "Drug Reaction":                 ["Dermatology", "Allergy", "General Physician"],
    "Peptic ulcer diseae":           ["Gastroenterology", "Gastroenterologist"],
    "AIDS":                          ["Infectious Disease", "General Physician"],
    "Diabetes":                      ["Endocrinology", "Endocrinologist", "Diabetology"],
    "Gastroenteritis":               ["Gastroenterology", "General Physician"],
    "Bronchial Asthma":              ["Pulmonology", "Respiratory", "Pulmonologist"],
    "Hypertension":                  ["Cardiology", "Cardiologist", "General Physician"],
    "Migraine":                      ["Neurology", "Neurologist"],
    "Cervical spondylosis":          ["Orthopedics", "Orthopedic", "Neurology"],
    "Paralysis (brain hemorrhage)":  ["Neurology", "Neurologist"],
    "Jaundice":                      ["Gastroenterology", "Hepatology", "General Physician"],
    "Malaria":                       ["Infectious Disease", "General Physician"],
    "Chicken pox":                   ["Dermatology", "General Physician", "Pediatrics"],
    "Dengue":                        ["Infectious Disease", "General Physician"],
    "Typhoid":                       ["Infectious Disease", "General Physician"],
    "hepatitis A":                   ["Gastroenterology", "Hepatology"],
    "Hepatitis B":                   ["Gastroenterology", "Hepatology"],
    "Hepatitis C":                   ["Gastroenterology", "Hepatology"],
    "Hepatitis D":                   ["Gastroenterology", "Hepatology"],
    "Hepatitis E":                   ["Gastroenterology", "Hepatology"],
    "Alcoholic hepatitis":           ["Gastroenterology", "Hepatology"],
    "Tuberculosis":                  ["Pulmonology", "Respiratory", "Infectious Disease"],
    "Common Cold":                   ["General Physician", "ENT"],
    "Pneumonia":                     ["Pulmonology", "Respiratory", "General Physician"],
    "Dimorphic hemmorhoids(piles)":  ["Gastroenterology", "Proctology", "General Surgery"],
    "Heart attack":                  ["Cardiology", "Cardiologist"],
    "Varicose veins":                ["Vascular Surgery", "General Surgery"],
    "Hypothyroidism":                ["Endocrinology", "Endocrinologist"],
    "Hyperthyroidism":               ["Endocrinology", "Endocrinologist"],
    "Hypoglycemia":                  ["Endocrinology", "Diabetology", "General Physician"],
    "Osteoarthritis":                ["Orthopedics", "Rheumatology", "Orthopedic"],
    "Arthritis":                     ["Rheumatology", "Orthopedics", "Orthopedic"],
    "(vertigo) Paroymsal  Positional Vertigo": ["ENT", "Neurology", "Neurologist"],
    "Acne":                          ["Dermatology", "Dermatologist"],
    "Urinary tract infection":       ["Urology", "Urologist", "General Physician"],
    "Psoriasis":                     ["Dermatology", "Dermatologist"],
    "Impetigo":                      ["Dermatology", "Dermatologist", "General Physician"],
}


def _get_recommended_doctors(disease_name, max_doctors=3):
    """Return up to max_doctors approved doctors matching the predicted disease's specialty."""
    keywords = DISEASE_SPECIALIZATION_MAP.get(disease_name, ["General Physician", "General"])

    from django.db.models import Q
    query = Q()
    for kw in keywords:
        query |= Q(specialization__icontains=kw)

    doctors = Doctor.objects.filter(query, is_approved=True).select_related("user")[:max_doctors]

    # Fallback: any approved doctor
    if not doctors.exists():
        doctors = Doctor.objects.filter(is_approved=True).select_related("user")[:max_doctors]

    return list(doctors)



def _extract_symptoms(message):
    """Extract symptom keywords from a free-text user message."""
    # Clean the message
    text = message.lower().strip()
    # Remove common filler words
    text = re.sub(r'\b(i have|i am|i\'m|having|feeling|experiencing|suffering from|got|with|and|also|the|a|an|my|me|very|really|quite|bit|little|some|been|for|days|weeks|since|yesterday|today)\b', ' ', text)
    # Replace punctuation with spaces
    text = re.sub(r'[,;.!?/\\()\[\]{}"\'"]', ' ', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Split into candidate tokens (single words and bigrams)
    words = text.split()
    candidates = list(words)
    # Add bigrams (e.g., "skin rash" → "skin_rash")
    for i in range(len(words) - 1):
        candidates.append(words[i] + "_" + words[i + 1])
    # Add trigrams
    for i in range(len(words) - 2):
        candidates.append(words[i] + "_" + words[i + 1] + "_" + words[i + 2])

    # Also try underscore versions of single words already containing underscores
    candidates.append(text.replace(" ", "_"))

    return candidates


# Minimum symptoms required before making a prediction
MIN_SYMPTOMS_FOR_PREDICTION = 5
# Maximum follow-up rounds
MAX_FOLLOWUP_ROUNDS = 3


def generate_response(message, request, patient=None):
    """Generate a disease prediction response using multi-step symptom collection."""

    msg_lower = message.lower().strip()

    # ── Handle reset/new commands ─────────────────────────────────────────
    if msg_lower in ("reset", "new", "start over", "clear", "restart"):
        request.session.pop('chat_symptoms', None)
        request.session.pop('chat_round', None)
        request.session.modified = True
        return """🔄 <strong>Conversation reset!</strong><br><br>
Please tell me your symptoms and I'll help predict possible conditions.<br>
<em>Example: "I have headache, fever, and nausea"</em>"""

    # ── Get or init session state ─────────────────────────────────────────
    session_symptoms = request.session.get('chat_symptoms', [])
    chat_round = request.session.get('chat_round', 0)

    # ── Check if user wants to force prediction ──────────────────────────
    force_predict = msg_lower in ("predict", "done", "yes predict", "show result", "show results", "result", "results")

    # ── Extract symptoms from current message ────────────────────────────
    if not force_predict:
        candidates = _extract_symptoms(message)
        new_matched, _ = match_symptoms(candidates)  # unpack (matched, unmatched) tuple
        
        # Add new symptoms to session (deduplicate)
        existing_set = set(session_symptoms)
        for s in new_matched:
            if s not in existing_set:
                session_symptoms.append(s)
                existing_set.add(s)

    # Save to session
    request.session['chat_symptoms'] = session_symptoms
    request.session.modified = True

    all_matched = session_symptoms

    # ── No symptoms at all ───────────────────────────────────────────────
    if not all_matched:
        return """I couldn't identify any symptoms from your message. Please describe your symptoms clearly.

<strong>Example:</strong> "I have headache, fever, and nausea"

You can also mention symptoms like: <em>itching, skin rash, cough, fatigue, vomiting, chest pain, joint pain</em>, etc."""

    # ── Decide: ask follow-up or predict ─────────────────────────────────
    should_predict = (
        force_predict or
        len(all_matched) >= MIN_SYMPTOMS_FOR_PREDICTION or
        chat_round >= MAX_FOLLOWUP_ROUNDS
    )

    if not should_predict:
        # Ask follow-up questions
        followup_symptoms = get_followup_symptoms(all_matched, max_suggestions=5)
        chat_round += 1
        request.session['chat_round'] = chat_round
        request.session.modified = True

        matched_display = ", ".join(s.replace("_", " ").title() for s in all_matched)
        
        if followup_symptoms:
            symptom_buttons = ""
            for sym in followup_symptoms:
                display_name = sym.replace("_", " ").title()
                symptom_buttons += (
                    f'<span class="symptom-chip-select" data-symptom="{sym}" '
                    f'onclick="toggleSymptomChip(this)" '
                    f'style="display:inline-block;background:linear-gradient(135deg,#EEF2FF,#E0E7FF);'
                    f'color:#4338CA;padding:6px 14px;border-radius:20px;margin:4px;cursor:pointer;'
                    f'font-size:0.9em;font-weight:500;border:2px solid #C7D2FE;transition:all 0.2s;'
                    f'user-select:none;">'
                    f'{display_name}</span>'
                )

            return f"""<div class="followup-container" style="max-width:100%;">
<div style="margin-bottom:10px;">
<strong>🩺 Symptoms noted so far:</strong> {matched_display}
</div>

<div style="margin-bottom:12px;">
To give you a more accurate prediction, do you also experience any of these symptoms?<br>
<small style="color:#6B7280;">Select one or more, then click <strong>Confirm</strong>.</small>
</div>

<div class="symptom-chips-group" style="margin-bottom:14px;">
{symptom_buttons}
</div>

<button class="confirm-symptoms-btn" onclick="confirmSelectedSymptoms(this)"
  style="display:none;background:linear-gradient(135deg,#5469FF,#4338CA);color:white;
  border:none;padding:8px 20px;border-radius:20px;cursor:pointer;font-size:0.9em;
  font-weight:600;margin-top:6px;transition:all 0.2s;box-shadow:0 4px 12px rgba(84,105,255,0.3);">
  ✅ Confirm Selection
</button>

<div style="margin-top:10px;font-size:0.85em;color:#6B7280;">
💡 <em>Or type more symptoms, or type <strong>"predict"</strong> to see results now.</em>
</div>
</div>"""
        else:
            # No follow-ups available, go ahead and predict
            should_predict = True

    # ── Final prediction ─────────────────────────────────────────────────
    if should_predict:
        result = predict_disease(all_matched)

        # Clear session after prediction
        request.session.pop('chat_symptoms', None)
        request.session.pop('chat_round', None)
        request.session.modified = True

        if result["disease"] is None:
            return f"""I couldn't match your symptoms to any known conditions in my database.

<strong>Try describing your symptoms using common terms like:</strong>
<ul>
<li>headache, fever, cough, fatigue, vomiting</li>
<li>skin rash, joint pain, chest pain, nausea</li>
<li>breathlessness, weight loss, dizziness</li>
</ul>

<em>Please try again with different symptom descriptions.</em>"""

        # Format matched symptoms for display
        matched_display = ", ".join(s.replace("_", " ").title() for s in result["matched_symptoms"])
        confidence_pct = f"{result['confidence'] * 100:.1f}%"

        # Build precautions list
        precaution_items = ""
        for i, p in enumerate(result["precautions"], 1):
            precaution_items += f"<li>{p.capitalize()}</li>"

        response = f"""<div style="margin-bottom: 12px;">
<strong>🔍 Predicted Condition:</strong> <span style="color: #5469FF; font-weight: 700; font-size: 1.05em;">{result['disease']}</span>
<br><small style="color: #6B7280;">Confidence: {confidence_pct}</small>
</div>

<div style="margin-bottom: 12px;">
<strong>📋 Description:</strong><br>
{result['description']}
</div>

<div style="margin-bottom: 12px;">
<strong>✅ Precautions:</strong>
<ol style="margin: 6px 0 0 18px; padding: 0;">
{precaution_items}
</ol>
</div>

<div style="margin-bottom: 12px;">
<strong>🩺 Matched Symptoms:</strong> {matched_display}
</div>

<div style="background: #FEF3C7; padding: 8px 12px; border-radius: 8px; margin-top: 8px; font-size: 0.85em;">
⚠️ <strong>Disclaimer:</strong> This is an AI-based prediction and NOT a medical diagnosis. Please consult a qualified healthcare professional for proper evaluation and treatment.
</div>

<div style="margin-top: 10px; font-size: 0.85em; color: #6B7280;">
🔄 <em>Type <strong>"new"</strong> to start a new symptom check.</em>
</div>"""

        # ── Doctor Recommendations ────────────────────────────────────────
        recommended_doctors = _get_recommended_doctors(result["disease"])

        if recommended_doctors:
            doctor_cards = ""
            for doc in recommended_doctors:
                name = doc.user.full_name or "Doctor"
                spec = doc.specialization or "Specialist"
                clinic = doc.clinic_name or "Clinic"
                exp = doc.years_of_experience
                exp_text = f"{exp} yrs exp" if exp else ""
                initial = name[0].upper() if name else "D"
                doctor_cards += f"""
<div style="display:flex;align-items:center;gap:12px;background:white;border:1px solid #E2E8F0;
border-radius:12px;padding:10px 14px;margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,0.05);
transition:box-shadow 0.2s;">
  <div style="width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,#5469FF,#4338CA);
  color:white;display:flex;align-items:center;justify-content:center;font-weight:700;
  font-size:1.1em;flex-shrink:0;">{initial}</div>
  <div style="flex:1;min-width:0;">
    <div style="font-weight:700;color:#0A2540;font-size:0.95em;">Dr. {name}</div>
    <div style="font-size:0.82em;color:#6B7280;">{spec} &bull; {clinic}{' &bull; ' + exp_text if exp_text else ''}</div>
  </div>
  <button onclick="openBookingModal('Dr. {name.replace("'", "\\'")}', '{spec.replace("'", "\\'")}', {doc.id}, '{patient.user.full_name.replace("'", "\\'") if patient and patient.user.full_name else ''}')" style="flex-shrink:0;background:linear-gradient(135deg,#14B8A6,#0D9488);
  color:white;padding:5px 12px;border-radius:20px;font-size:0.8em;font-weight:600;
  border:none;cursor:pointer;white-space:nowrap;">Book →</button>
</div>"""

            doc_section = f"""
<div style="margin-top:16px;padding-top:14px;border-top:2px solid #EEF2FF;">
<div style="font-weight:700;color:#0A2540;margin-bottom:10px;font-size:0.95em;">
👨‍⚕️ Recommended Doctors for <span style="color:#5469FF;">{result['disease']}</span>
</div>
{doctor_cards}
<div style="font-size:0.8em;color:#6B7280;margin-top:4px;">
💡 <a href="/patient/all-doctors/" style="color:#5469FF;text-decoration:none;font-weight:600;">View all doctors →</a>
</div>
</div>"""
        else:
            doc_section = """
<div style="margin-top:14px;font-size:0.85em;color:#6B7280;">
👨‍⚕️ No specific doctors found. <a href="/patient/all-doctors/" style="color:#5469FF;font-weight:600;text-decoration:none;">Browse all doctors →</a>
</div>"""

        response += doc_section
        return response

    return """Something went wrong. Please type <strong>"reset"</strong> to start over."""
