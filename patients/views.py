from django.shortcuts import render, redirect
from django.http import JsonResponse
from patients.models import Patient
from users.models import User
import json
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

        doctors = Doctor.objects.select_related("user").all()[:6]

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

        appointments = Appointment.objects.filter(patient=patient, status='Booked').select_related("doctor__user")
        cancelled_appointments = Appointment.objects.filter(patient=patient, status='Cancelled').select_related("doctor__user")
        completed_appointments = Appointment.objects.filter(patient=patient, status='Completed').select_related("doctor__user")

        upcoming_count = appointments.count()
        cancelled_count = cancelled_appointments.count()
        completed_count = completed_appointments.count()


        context = {
            "user": user,
            "patient": patient,
            "doctors": doctors,
            "appointments": appointments,
            "cancelled_appointments": cancelled_appointments,
            "completed_appointments": completed_appointments,
            "upcoming_count": upcoming_count,
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
    """Handle chat messages via AJAX"""
    
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
            chat_id = data.get('chat_id', None)
            
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
            
            # Generate AI response
            # TODO: Replace with your ML model
            bot_response = generate_response(user_message, patient)
            
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



def generate_response(message,patient = None):
    """Simple response generator - replace with your ML model"""
    message_lower = message.lower()
    
    if 'fever' in message_lower:
        return """I understand you're experiencing fever. This could indicate an infection.

**Recommendations:**
- Monitor your temperature regularly
- Stay hydrated and rest
- Take fever reducers if needed
- If fever persists above 103°F or lasts 3+ days, consult a doctor

Can you tell me about any other symptoms?"""
    
    elif 'cough' in message_lower:
        return """A persistent cough can have various causes.

**Recommendations:**
- Stay hydrated
- Use a humidifier
- Avoid irritants
- If cough persists 2+ weeks, see a doctor

Are you experiencing fever or shortness of breath?"""
    
    else:
        return """Thank you for sharing. To provide better recommendations:

1. How long have you had these symptoms?
2. On a scale of 1-10, how severe?
3. Any patterns or triggers?

This will help me provide accurate guidance."""
