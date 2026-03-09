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

        return render(request, "patient/patient.html", {
            "patient": patient,
            "user": user,
            "saved": True
        })

    return render(request, "patient/patient.html", {
        "patient": patient,
        "user": user,
        "saved": False
    })


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
            'patient': patient
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