from django.shortcuts import render, redirect, get_object_or_404
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

        patient.blood_group      = request.POST.get("blood_group", "")
        patient.emergency_contact = request.POST.get("emergency_contact", "")

        height = request.POST.get("height_cm", "").strip()
        weight = request.POST.get("weight_kg", "").strip()
        age    = request.POST.get("age", "").strip()

        patient.height_cm = int(height) if height else None
        patient.weight_kg = int(weight) if weight else None
        patient.age       = int(age)    if age    else None

        try:
            patient.save()
            print("Saved successfully!")
        except Exception as e:
            logger.error("Save failed: %s", e)

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
        user    = User.objects.get(id=request.session["user_id"])
        patient = Patient.objects.filter(user=user).first()
        doctors = Doctor.objects.select_related("user").all()

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

        doctors = doctors[:6]

        appointments           = Appointment.objects.filter(patient=patient, status='Booked').select_related("doctor__user")
        pending_appointments   = Appointment.objects.filter(patient=patient, status='Pending').select_related("doctor__user")
        cancelled_appointments = Appointment.objects.filter(patient=patient, status='Cancelled').select_related("doctor__user")
        completed_appointments = Appointment.objects.filter(patient=patient, status='Completed').select_related("doctor__user")

        upcoming_count  = appointments.count()
        pending_count   = pending_appointments.count()
        cancelled_count = cancelled_appointments.count()
        completed_count = completed_appointments.count()

        for appt in cancelled_appointments:
            if "\n\n[CANCEL_REASON]" in appt.reason_for_visit:
                parts = appt.reason_for_visit.split("\n\n[CANCEL_REASON]")
                appt.display_reason = parts[0]
                appt.cancel_reason  = parts[1]
            else:
                appt.display_reason = appt.reason_for_visit
                appt.cancel_reason  = "No reason provided."
                
        from appointments.models import MedicalReport
        medical_reports = MedicalReport.objects.filter(patient=patient).order_by('-created_at')

        context = {
            "user": user, "patient": patient, "doctors": doctors,
            "appointments": appointments,
            "pending_appointments": pending_appointments,
            "cancelled_appointments": cancelled_appointments,
            "completed_appointments": completed_appointments,
            "upcoming_count": upcoming_count,
            "pending_count": pending_count,
            "cancelled_count": cancelled_count,
            "completed_count": completed_count,
            "medical_reports": medical_reports,
            "notifications_count": 0
        }

        return render(request, "patient/patient_dashboard.html", context)

    except User.DoesNotExist:
        return redirect("login")


def all_doctors(request):
    if request.session.get("role") != "Patient":
        return redirect("login")

    try:
        user    = User.objects.get(id=request.session["user_id"])
        patient = Patient.objects.filter(user=user).first()
        doctors = Doctor.objects.select_related("user").all()

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
            "user": user, "patient": patient,
            "doctors": doctors, "notifications_count": 0
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
            date      = data.get("date")
            time_str  = data.get("time")
            reason    = data.get("reason")

            appointment_time = datetime.strptime(time_str, "%I:%M %p").time()

            patient = Patient.objects.get(user_id=request.session["user_id"])
            doctor  = Doctor.objects.get(id=doctor_id)

            if Appointment.objects.filter(
                doctor=doctor,
                appointment_date=date,
                appointment_time=appointment_time
            ).exists():
                return JsonResponse({"success": False, "error": "Slot already booked"})

            appt = Appointment.objects.create(
                patient=patient,
                doctor=doctor,
                appointment_date=date,
                appointment_time=appointment_time,
                reason_for_visit=reason,
                status='Pending'
            )

            # Link the newly created appointment to the patient's latest unlinked medical report (if one was generated during chat)
            from appointments.models import MedicalReport
            latest_report = MedicalReport.objects.filter(patient=patient, appointment__isnull=True).order_by('-created_at').first()
            if latest_report:
                latest_report.appointment = appt
                latest_report.save()

            return JsonResponse({"success": True})

        except Exception as e:
            print("ERROR:", e)
            return JsonResponse({"success": False})


# ==================== CHAT VIEWS ====================

def chat_view(request):
    """Patient chat interface"""
    if request.session.get("role") != "Patient":
        return redirect("login")

    try:
        user    = User.objects.get(id=request.session["user_id"])
        patient = Patient.objects.filter(user=user).first()

        return render(request, 'patient/healsmart_professional_chat.html', {
            'user': user, 'patient': patient, 'notifications_count': 0
        })
    except User.DoesNotExist:
        return redirect("login")


def chat_api(request):
    """Handle chat messages via AJAX - multi-step symptom collection."""
    if request.session.get("role") != "Patient":
        return JsonResponse({'success': False, 'error': 'Please login to continue'}, status=401)

    if request.method == 'POST':
        try:
            data         = json.loads(request.body)
            user_message = data.get('message', '').strip()

            if not user_message:
                return JsonResponse({'success': False, 'error': 'Message cannot be empty'}, status=400)

            user    = User.objects.get(id=request.session["user_id"])
            patient = Patient.objects.filter(user=user).first()

            logger.info("Patient %s said: %s", user.full_name, user_message)

            result = generate_response(user_message, request, patient)

            # generate_response returns either a plain string OR a dict with report_id
            if isinstance(result, dict):
                return JsonResponse({
                    'success': True,
                    'response': result['html'],
                    'report_id': result.get('report_id')
                })
            else:
                return JsonResponse({'success': True, 'response': result})

        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        except Exception as e:
            import traceback
            logger.error("Chat API error: %s\n%s", str(e), traceback.format_exc())
            print(f"CHAT API ERROR: {e}")
            print(traceback.format_exc())
            return JsonResponse({'success': False, 'error': 'Something went wrong. Please try again.'}, status=500)

    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


# ==================== MEDICAL REPORT DOWNLOAD ====================

def download_report(request, report_id):
    """Render a printable HTML medical report page."""
    if request.session.get("role") not in ("Patient", "Admin"):
        return redirect("login")

    from appointments.models import MedicalReport
    report = get_object_or_404(MedicalReport, id=report_id)

    # Parse precautions JSON
    try:
        precautions_list = json.loads(report.precautions) if report.precautions else []
    except Exception:
        precautions_list = [p.strip() for p in report.precautions.split(',') if p.strip()]

    # Parse diet plan JSON
    diet_plan_dict = {}
    if getattr(report, 'diet_plan', None):
        try:
            diet_plan_dict = json.loads(report.diet_plan)
        except Exception:
            pass

    symptoms_list = [s.strip().replace('_', ' ').title() for s in report.symptoms.split(',') if s.strip()]

    # Get doctor from linked appointment if available
    doctor = None
    if report.appointment:
        doctor = report.appointment.doctor

    return render(request, 'patient/medical_report_print.html', {
        'report': report,
        'patient': report.patient,
        'doctor': doctor,
        'symptoms_list': symptoms_list,
        'precautions_list': precautions_list,
        'diet_plan': diet_plan_dict,
    })


# ==================== CHAT LOGIC ====================

import re
import sys
from doctors.models import Doctor

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from prediction_model.predict import predict_disease, match_symptoms, get_followup_symptoms, _symptoms_list


# Disease -> Specialization mapping
DISEASE_SPECIALIZATION_MAP = {
    "Fungal infection":                         ["Dermatology", "Dermatologist"],
    "Allergy":                                  ["Allergy", "Immunology", "ENT"],
    "GERD":                                     ["Gastroenterology", "Gastroenterologist"],
    "Chronic cholestasis":                      ["Gastroenterology", "Hepatology"],
    "Drug Reaction":                            ["Dermatology", "Allergy", "General Physician"],
    "Peptic ulcer diseae":                      ["Gastroenterology", "Gastroenterologist"],
    "AIDS":                                     ["Infectious Disease", "General Physician"],
    "Diabetes":                                 ["Endocrinology", "Endocrinologist", "Diabetology"],
    "Gastroenteritis":                          ["Gastroenterology", "General Physician"],
    "Bronchial Asthma":                         ["Pulmonology", "Respiratory", "Pulmonologist"],
    "Hypertension":                             ["Cardiology", "Cardiologist", "General Physician"],
    "Migraine":                                 ["Neurology", "Neurologist"],
    "Cervical spondylosis":                     ["Orthopedics", "Orthopedic", "Neurology"],
    "Paralysis (brain hemorrhage)":             ["Neurology", "Neurologist"],
    "Jaundice":                                 ["Gastroenterology", "Hepatology", "General Physician"],
    "Malaria":                                  ["Infectious Disease", "General Physician"],
    "Chicken pox":                              ["Dermatology", "General Physician", "Pediatrics"],
    "Dengue":                                   ["Infectious Disease", "General Physician"],
    "Typhoid":                                  ["Infectious Disease", "General Physician"],
    "hepatitis A":                              ["Gastroenterology", "Hepatology"],
    "Hepatitis B":                              ["Gastroenterology", "Hepatology"],
    "Hepatitis C":                              ["Gastroenterology", "Hepatology"],
    "Hepatitis D":                              ["Gastroenterology", "Hepatology"],
    "Hepatitis E":                              ["Gastroenterology", "Hepatology"],
    "Alcoholic hepatitis":                      ["Gastroenterology", "Hepatology"],
    "Tuberculosis":                             ["Pulmonology", "Respiratory", "Infectious Disease"],
    "Common Cold":                              ["General Physician", "ENT"],
    "Pneumonia":                                ["Pulmonology", "Respiratory", "General Physician"],
    "Dimorphic hemmorhoids(piles)":             ["Gastroenterology", "Proctology", "General Surgery"],
    "Heart attack":                             ["Cardiology", "Cardiologist"],
    "Varicose veins":                           ["Vascular Surgery", "General Surgery"],
    "Hypothyroidism":                           ["Endocrinology", "Endocrinologist"],
    "Hyperthyroidism":                          ["Endocrinology", "Endocrinologist"],
    "Hypoglycemia":                             ["Endocrinology", "Diabetology", "General Physician"],
    "Osteoarthritis":                           ["Orthopedics", "Rheumatology", "Orthopedic"],
    "Arthritis":                                ["Rheumatology", "Orthopedics", "Orthopedic"],
    "(vertigo) Paroymsal  Positional Vertigo":  ["ENT", "Neurology", "Neurologist"],
    "Acne":                                     ["Dermatology", "Dermatologist"],
    "Urinary tract infection":                  ["Urology", "Urologist", "General Physician"],
    "Psoriasis":                                ["Dermatology", "Dermatologist"],
    "Impetigo":                                 ["Dermatology", "Dermatologist", "General Physician"],
}


def _get_recommended_doctors(disease_name, max_doctors=3):
    """Return approved doctors whose specialty matches the predicted disease."""
    keywords = DISEASE_SPECIALIZATION_MAP.get(disease_name, ["General Physician", "General"])

    from django.db.models import Q
    query = Q()
    for kw in keywords:
        query |= Q(specialization__icontains=kw)

    doctors = Doctor.objects.filter(query, is_approved=True).select_related("user")[:max_doctors]

    if not doctors.exists():
        doctors = Doctor.objects.filter(is_approved=True).select_related("user")[:max_doctors]

    return list(doctors)


def _extract_symptoms(message):
    """Extract symptom keywords from a free-text user message."""
    text = message.lower().strip()

    original_clean = re.sub(r'[,;.!?/\\()\[\]{}"\'"]', ' ', text)
    original_clean = re.sub(r'\s+', ' ', original_clean).strip()

    text_stripped = re.sub(
        r'\b(i have|i am|i\'m|having|feeling|experiencing|suffering from|'
        r'got|with|and|also|the|a|an|my|me|very|really|quite|bit|little|'
        r'some|been|for|days|weeks|since|yesterday|today|mujhe|mujhe hai|'
        r'ho raha hai|ho rahi hai|ho rahe hain|hai|hain|se|mein|ka|ki|ke)\b',
        ' ', text
    )
    text_stripped = re.sub(r'[,;.!?/\\()\[\]{}"\'"]', ' ', text_stripped)
    text_stripped = re.sub(r'\s+', ' ', text_stripped).strip()

    words = text_stripped.split()

    candidates = []
    candidates.extend(words)

    for i in range(len(words) - 1):
        candidates.append(words[i] + "_" + words[i + 1])

    for i in range(len(words) - 2):
        candidates.append(words[i] + "_" + words[i + 1] + "_" + words[i + 2])

    candidates.append(original_clean.replace(" ", "_"))

    orig_words = original_clean.split()
    for i in range(len(orig_words) - 1):
        candidates.append(orig_words[i] + "_" + orig_words[i + 1])
    for i in range(len(orig_words) - 2):
        candidates.append(orig_words[i] + "_" + orig_words[i + 1] + "_" + orig_words[i + 2])

    return candidates


MIN_SYMPTOMS_FOR_PREDICTION = 4
MAX_FOLLOWUP_ROUNDS = 3


def generate_response(message, request, patient=None):
    """Generate disease prediction response - multi-step symptom collection."""

    msg_lower = message.lower().strip()

    # Reset / New conversation
    if msg_lower in ("reset", "new", "start over", "clear", "restart", "dobara", "phir se"):
        request.session.pop('chat_symptoms', None)
        request.session.pop('chat_round', None)
        request.session.modified = True
        return (
            "<strong>Conversation reset!</strong><br><br>\n"
            "Please describe your symptoms and I'll help predict possible conditions.<br>\n"
            "<em>Example: \"I have headache, fever, and nausea\"</em>"
        )

    # Session state
    session_symptoms = request.session.get('chat_symptoms', [])
    chat_round       = request.session.get('chat_round', 0)

    # Force predict commands (including common Hinglish shorthand users may type)
    force_predict = msg_lower in (
        "predict", "done", "yes predict", "show result", "show results",
        "result", "results", "batao", "predict karo", "bata do"
    )

    # Extract symptoms from the current message
    if not force_predict:
        candidates           = _extract_symptoms(message)
        new_matched, new_unmatched = match_symptoms(candidates)

        existing_set = set(session_symptoms)
        for s in new_matched:
            if s not in existing_set:
                session_symptoms.append(s)
                existing_set.add(s)

        if not new_matched and not session_symptoms:
            unmatched_display = []
            for raw in new_unmatched[:3]:
                clean = raw.replace("_", " ")
                if len(clean) > 3:
                    unmatched_display.append('<em>"%s"</em>' % clean)

            unmatched_hint = ""
            if unmatched_display:
                unmatched_hint = (
                    "<br><br>\n"
                    '<div style="background:#FEF3C7;padding:8px 12px;border-radius:8px;font-size:0.85em;">\n'
                    "Could not identify these words: %s<br>\n"
                    "<strong>Try using:</strong> headache, fever, cough, fatigue, nausea, joint pain, skin rash, chest pain, vomiting, dizziness\n"
                    "</div>"
                ) % (', '.join(unmatched_display),)

            return (
                "No recognized symptoms found in your message.%s\n\n"
                "<strong>Examples:</strong>\n"
                "<ul>\n"
                '<li>"I have headache, fever, and body pain"</li>\n'
                '<li>"frequent urination, extreme thirst, fatigue"</li>\n'
                '<li>"itching, skin rash, nausea, vomiting"</li>\n'
                "</ul>"
            ) % (unmatched_hint,)

    # Save updated symptoms to session
    request.session['chat_symptoms'] = session_symptoms
    request.session.modified         = True

    all_matched = session_symptoms

    # No symptoms collected at all
    if not all_matched:
        return (
            "No symptoms could be identified. Please describe your symptoms clearly.\n\n"
            "<strong>Example:</strong> \"I have headache, fever, and nausea\"\n\n"
            "Common symptoms: <em>itching, skin rash, cough, fatigue, vomiting, chest pain, joint pain, dizziness, diarrhoea</em>"
        )

    # Predict karna chahiye ya follow-up
    should_predict = (
        force_predict
        or len(all_matched) >= MIN_SYMPTOMS_FOR_PREDICTION
        or chat_round >= MAX_FOLLOWUP_ROUNDS
    )

    if not should_predict:
        followup_symptoms = get_followup_symptoms(all_matched, max_suggestions=5)
        chat_round += 1
        request.session['chat_round'] = chat_round
        request.session.modified      = True

        matched_display = ", ".join(s.replace("_", " ").title() for s in all_matched)

        if followup_symptoms:
            symptom_buttons = ""
            for sym in followup_symptoms:
                display_name = sym.replace("_", " ").title()
                symptom_buttons += (
                    '<span class="symptom-chip-select" data-symptom="%s" '
                    'onclick="toggleSymptomChip(this)" '
                    'style="display:inline-block;background:linear-gradient(135deg,#EEF2FF,#E0E7FF);'
                    'color:#4338CA;padding:6px 14px;border-radius:20px;margin:4px;cursor:pointer;'
                    'font-size:0.9em;font-weight:500;border:2px solid #C7D2FE;transition:all 0.2s;'
                    'user-select:none;">'
                    '%s</span>'
                ) % (sym, display_name)

            return (
                '<div class="followup-container" style="max-width:100%;">\n'
                '<div style="margin-bottom:10px;">\n'
                '<strong>Symptoms noted so far:</strong> ' + matched_display + '\n'
                '</div>\n\n'
                '<div style="margin-bottom:12px;">\n'
                'To give a more accurate prediction - do you also have any of these symptoms?<br>\n'
                '<small style="color:#6B7280;">Select one or more, then click <strong>Confirm</strong>.</small>\n'
                '</div>\n\n'
                '<div class="symptom-chips-group" style="margin-bottom:14px;">\n'
                + symptom_buttons + '\n'
                '</div>\n\n'
                '<button class="confirm-symptoms-btn" onclick="confirmSelectedSymptoms(this)"\n'
                '  style="display:none;background:linear-gradient(135deg,#5469FF,#4338CA);color:white;\n'
                '  border:none;padding:8px 20px;border-radius:20px;cursor:pointer;font-size:0.9em;\n'
                '  font-weight:600;margin-top:6px;transition:all 0.2s;box-shadow:0 4px 12px rgba(84,105,255,0.3);">\n'
                '  Confirm Selection\n'
                '</button>\n\n'
                '<div style="margin-top:10px;font-size:0.85em;color:#6B7280;">\n'
                '<em>Or type more symptoms, or type <strong>"predict"</strong> to see results now.</em>\n'
                '</div>\n'
                '</div>'
            )
        else:
            should_predict = True

    # Final prediction
    if should_predict:
        result = predict_disease(all_matched)

        # Clear session after prediction is complete
        request.session.pop('chat_symptoms', None)
        request.session.pop('chat_round', None)
        request.session.modified = True

        if result["disease"] is None:
            return (
                "Could not match your symptoms to any known condition.\n\n"
                "<strong>Try using common terms like:</strong>\n"
                "<ul>\n"
                "<li>headache, fever, cough, fatigue, vomiting</li>\n"
                "<li>skin rash, joint pain, chest pain, nausea</li>\n"
                "<li>breathlessness, weight loss, dizziness</li>\n"
                "</ul>\n\n"
                "<em>Please try again with different symptom descriptions.</em>"
            )

        matched_display = ", ".join(s.replace("_", " ").title() for s in result["matched_symptoms"])
        confidence_pct  = "%.1f%%" % (result['confidence'] * 100)

        # Unmatched symptoms feedback
        unmatched_feedback = ""
        if result["unmatched_symptoms"]:
            unmatched_clean = [
                u.replace("_", " ") for u in result["unmatched_symptoms"]
                if len(u.replace("_", " ")) > 3
            ][:4]
            if unmatched_clean:
                unmatched_feedback = (
                    '<div style="background:#F0F9FF;padding:8px 12px;border-radius:8px;margin-bottom:10px;font-size:0.83em;color:#0369A1;">\n'
                    '<strong>These symptoms could not be recognized:</strong> %s<br>\n'
                    'Try describing them using different words for better accuracy.\n'
                    '</div>'
                ) % (', '.join('"%s"' % s for s in unmatched_clean),)

        # Low confidence warning
        confidence_warning = ""
        if result["low_confidence"]:
            alt_diseases = ""
            for alt in result["top3"][1:]:
                alt_diseases += "<li>%s (%.0f%%)</li>" % (alt["disease"], alt["confidence"] * 100)

            confidence_warning = (
                '<div style="background:#FEF3C7;padding:10px 14px;border-radius:8px;margin-bottom:12px;font-size:0.88em;">\n'
                '<strong>Low Confidence (%s)</strong> - The model is not very certain.<br>\n'
                'Your symptoms match multiple conditions. Please describe more symptoms for a better result.<br>\n'
                '<strong>Other possibilities:</strong><ul style="margin:4px 0 0 16px;padding:0;">%s</ul>\n'
                '<em>Please consult a doctor for a proper diagnosis.</em>\n'
                '</div>'
            ) % (confidence_pct, alt_diseases)

        # Precautions list
        precaution_items = "".join(
            "<li>%s</li>" % p.capitalize()
            for p in result["precautions"]
        )

        # ── Diet Plan section ──────────────────────────────────────────────────
        diet = result.get("diet_plan", {})

        if diet and any(diet.get(k) for k in ("breakfast", "lunch", "dinner", "general_tips")):

            def _diet_row(icon, label, value):
                """Helper: build one diet row (icon + label + value)."""
                if not value:
                    return ""
                return (
                    '<div style="display:flex;gap:10px;margin-bottom:8px;align-items:flex-start;">'
                    '<span style="font-size:1.1em;min-width:22px;">{icon}</span>'
                    '<div><strong style="color:#065F46;">{label}:</strong> '
                    '<span style="color:#374151;">{value}</span></div>'
                    '</div>'
                ).format(icon=icon, label=label, value=value)

            diet_rows = (
                _diet_row("🌅", "Breakfast", diet.get("breakfast", ""))
                + _diet_row("☀️",  "Lunch",     diet.get("lunch",     ""))
                + _diet_row("🌙", "Dinner",    diet.get("dinner",    ""))
            )

            avoid_section = ""
            if diet.get("foods_to_avoid"):
                avoid_section = (
                    '<div style="background:#FEF2F2;border-left:3px solid #EF4444;'
                    'padding:8px 12px;border-radius:0 8px 8px 0;margin-top:8px;">'
                    '<strong style="color:#B91C1C;">🚫 Avoid:</strong> '
                    '<span style="color:#374151;font-size:0.92em;">%s</span>'
                    '</div>'
                ) % diet["foods_to_avoid"]

            tips_section = ""
            if diet.get("general_tips"):
                tips_section = (
                    '<div style="background:#ECFDF5;border-left:3px solid #10B981;'
                    'padding:8px 12px;border-radius:0 8px 8px 0;margin-top:8px;">'
                    '<strong style="color:#065F46;">💡 Tips:</strong> '
                    '<span style="color:#374151;font-size:0.92em;">%s</span>'
                    '</div>'
                ) % diet["general_tips"]

            diet_section_html = (
                '<div style="margin-bottom:14px;background:#F0FDF4;border:1px solid #86EFAC;'
                'border-radius:12px;padding:14px;">\n'
                '<div style="font-weight:700;color:#14532D;margin-bottom:10px;font-size:0.97em;">'
                '🥗 Recommended Diet Plan</div>\n'
                + diet_rows
                + avoid_section
                + tips_section
                + '\n</div>\n'
            )
        else:
            diet_section_html = (
                '<div style="margin-bottom:12px;background:#F0FDF4;border:1px solid #86EFAC;'
                'border-radius:12px;padding:12px;font-size:0.88em;color:#065F46;">'
                '🥗 <strong>Diet Tip:</strong> Eat a balanced nutritious diet and consult a '
                'registered dietitian for a personalized plan for <strong>%s</strong>.'
                '</div>\n'
            ) % result['disease']

        # ── Full response assembly ─────────────────────────────────────────────
        response = (
            unmatched_feedback
            + confidence_warning
            + '<div style="margin-bottom: 12px;">\n'
            + '<strong>Predicted Condition:</strong> <span style="color: #5469FF; font-weight: 700; font-size: 1.05em;">'
            + result['disease']
            + '</span>\n<br><small style="color: #6B7280;">Confidence: '
            + confidence_pct
            + '</small>\n</div>\n\n'
            + '<div style="margin-bottom: 12px;">\n'
            + '<strong>Description:</strong><br>\n'
            + result['description']
            + '\n</div>\n\n'
            + '<div style="margin-bottom: 12px;">\n'
            + '<strong>Precautions:</strong>\n'
            + '<ol style="margin: 6px 0 0 18px; padding: 0;">\n'
            + precaution_items
            + '\n</ol>\n</div>\n\n'
            + diet_section_html
            + '<div style="margin-bottom: 12px;">\n'
            + '<strong>Matched Symptoms:</strong> '
            + matched_display
            + '\n</div>\n\n'
            + '<div style="background: #FEF3C7; padding: 8px 12px; border-radius: 8px; margin-top: 8px; font-size: 0.85em;">\n'
            + '<strong>Disclaimer:</strong> This is an AI-based prediction and NOT a medical diagnosis. Please consult a qualified healthcare professional.\n'
            + '</div>\n\n'
            + '<div style="margin-top: 10px; font-size: 0.85em; color: #6B7280;">\n'
            + '<em>Type <strong>"new"</strong> to start a new symptom check.</em>\n'
            + '</div>'
        )

        # Doctor Recommendations
        recommended_doctors = _get_recommended_doctors(result["disease"])

        if recommended_doctors:
            doctor_cards = ""
            for doc in recommended_doctors:
                name     = doc.user.full_name or "Doctor"
                spec     = doc.specialization or "Specialist"
                clinic   = doc.clinic_name or "Clinic"
                exp      = doc.years_of_experience
                exp_text = "%s yrs exp" % exp if exp else ""
                initial  = name[0].upper() if name else "D"
                patient_name = patient.user.full_name.replace("'", "\\'") if patient and patient.user.full_name else ""
                exp_part = " &bull; %s" % exp_text if exp_text else ""
                doctor_cards += (
                    '<div style="display:flex;align-items:center;gap:12px;background:white;border:1px solid #E2E8F0;'
                    'border-radius:12px;padding:10px 14px;margin-bottom:8px;box-shadow:0 2px 8px rgba(0,0,0,0.05);">\n'
                    '  <div style="width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,#5469FF,#4338CA);'
                    '  color:white;display:flex;align-items:center;justify-content:center;font-weight:700;'
                    '  font-size:1.1em;flex-shrink:0;">%s</div>\n'
                    '  <div style="flex:1;min-width:0;">\n'
                    '    <div style="font-weight:700;color:#0A2540;font-size:0.95em;">Dr. %s</div>\n'
                    '    <div style="font-size:0.82em;color:#6B7280;">%s &bull; %s%s</div>\n'
                    '  </div>\n'
                    '  <button onclick="openBookingModal(\'Dr. %s\', \'%s\', %s, \'%s\')"\n'
                    '  style="flex-shrink:0;background:linear-gradient(135deg,#14B8A6,#0D9488);'
                    '  color:white;padding:5px 12px;border-radius:20px;font-size:0.8em;font-weight:600;'
                    '  border:none;cursor:pointer;white-space:nowrap;">Book</button>\n'
                    '</div>'
                ) % (
                    initial, name,
                    spec, clinic, exp_part,
                    name.replace("'", "\\'"), spec.replace("'", "\\'"), doc.id, patient_name
                )

            doc_section = (
                '<div style="margin-top:16px;padding-top:14px;border-top:2px solid #EEF2FF;">\n'
                '<div style="font-weight:700;color:#0A2540;margin-bottom:10px;font-size:0.95em;">\n'
                'Recommended Doctors for <span style="color:#5469FF;">%s</span>\n'
                '</div>\n'
                '%s\n'
                '<div style="font-size:0.8em;color:#6B7280;margin-top:4px;">\n'
                '<a href="/patient/all-doctors/" style="color:#5469FF;text-decoration:none;font-weight:600;">View all doctors</a>\n'
                '</div>\n'
                '</div>'
            ) % (result['disease'], doctor_cards)
        else:
            doc_section = (
                '<div style="margin-top:14px;font-size:0.85em;color:#6B7280;">\n'
                'No specific doctors found. <a href="/patient/all-doctors/" style="color:#5469FF;font-weight:600;text-decoration:none;">Browse all doctors</a>\n'
                '</div>'
            )

        response += doc_section

        # Save MedicalReport to DB
        report_id = None
        if patient:
            try:
                from appointments.models import MedicalReport

                medical_report = MedicalReport.objects.create(
                    patient=patient,
                    appointment=None,

                    symptoms=", ".join(result["matched_symptoms"]),
                    predicted_disease=result["disease"],
                    disease_description=result.get("description", ""),
                    precautions=json.dumps(result.get("precautions", [])),
                    diet_plan=json.dumps(result.get("diet_plan", {})),
                    confidence=result["confidence"],
                )
                report_id = medical_report.id
            except Exception as e:
                logger.error("MedicalReport save error: %s", e)

        # Return dict so chat_api can include report_id in JSON
        return {'html': response, 'report_id': report_id}

    return 'Something went wrong. Please type <strong>"reset"</strong> to start over.'