# Create your views here.
from django.shortcuts import render, redirect
from doctors.models import Doctor
from users.models import User

def doctor_page(request):
    # 🔐 Role protection
    if request.session.get("role") != "Doctor":
        return redirect("login")

    user_id = request.session.get("user_id")
    user = User.objects.get(id=user_id)

    # ✅ create doctor row if not exists
    doctor, created = Doctor.objects.get_or_create(
        user=user,
        defaults={ "name": user.full_name }
    )

   

    if request.method == "POST":
        doctor.name = request.POST.get("name", doctor.name)
        doctor.age = request.POST.get("age")
        doctor.qualifications = request.POST.get("qualifications")
        doctor.specialization = request.POST.get("specialization")
        doctor.years_of_experience = request.POST.get("years_of_experience")
        doctor.clinic_name = request.POST.get("clinic_name")
        doctor.save()

        if not doctor.is_approved:
            request.session.flush()
            return render(request, "login/login.html", {
                "success_msg": "Registration successful! Your professional details have been saved. Please wait for admin approval before logging in."
            })

        return redirect("doctor_dashboard")


    return render(request, "doctor/doctor.html", {
        "doctor": doctor,
        "saved" : not created
    })
# doctors/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.db.models import Q, Count
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from doctors.models import Doctor
from appointments.models import Appointment
from patients.models import Patient
from users.models import User
import json
import logging

logger = logging.getLogger(__name__)


def doctor_dashboard(request):
    """
    Main doctor dashboard view with statistics and appointments
    """
    # Check if user is logged in as doctor
    if request.session.get("role") != "Doctor":
        return redirect("login")
    
    try:
        # Get doctor instance
        user = User.objects.get(id=request.session["user_id"])
        doctor = Doctor.objects.filter(user=user).first()
        
        if not doctor:
            logger.error(f"Doctor profile not found for user {user.id}")
            return redirect("login")
            
        if not doctor.is_approved:
            request.session.flush()
            return redirect("login")
        
        today = date.today()
        last_week = today - timedelta(days=7)
        next_week = today + timedelta(days=7)
        
        # Get all unique patients who have appointments with this doctor
        all_patients = Patient.objects.filter(
            appointment__doctor=doctor
        ).distinct()
        
        total_patients = all_patients.count()
        
        # Today's appointments
        today_appointments = Appointment.objects.filter (
            doctor=doctor,
            appointment_date=today,
            status='Booked',  # only show approved appointments
        
        ).exclude(status='Cancelled').select_related('patient__user').order_by('appointment_time')
        
        today_appointments_count = today_appointments.count()
        
        # Confirmed appointments today
        confirmed_today_count = today_appointments.filter(status='Booked').count()
        
        # Pending appointments (within next week)
        pending_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='Pending',
            appointment_date__lte=next_week
        ).select_related('patient__user').order_by('appointment_date', 'appointment_time')
        
        pending_appointments_count = pending_appointments.count()
        
        # Upcoming appointments (next 7 days, confirmed)
        upcoming_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gt=today,
            appointment_date__lte=next_week,
            status='Booked'
        ).select_related('patient__user').order_by('appointment_date', 'appointment_time')
        
        # Previous appointments (past 7 days)
        now = datetime.now()

        previous_appointments = Appointment.objects.filter(
            doctor=doctor,
            appointment_date__gte=last_week
        ).filter(
            Q(appointment_date__lt=today) |
            Q(appointment_date=today, appointment_time__lt=now.time()) |
            Q(status='Completed')
        ).exclude(status='Cancelled').select_related('patient__user').order_by('-appointment_date', '-appointment_time')

        # Completed appointments this month -> change to this week
        today = date.today()
        now = timezone.now()

        # AUTO COMPLETE PAST APPOINTMENTS (update DB)
        Appointment.objects.filter(
            doctor=doctor,
            status='Booked',
            appointment_date__lt=now.date()
        ).update(status='Completed')

        Appointment.objects.filter(
            doctor=doctor,
            status='Booked',
            appointment_date=now.date(),
            appointment_time__lt=now.time()
        ).update(status='Completed')


        # COMPLETED APPOINTMENTS THIS WEEK
        completed_queryset = Appointment.objects.filter(
            doctor=doctor,
            status='Completed',
            appointment_date__gte=last_week,
            appointment_date__lte=today
        )

        completed_appointments_count = completed_queryset.count()

        completed_appointments = completed_queryset.select_related(
            'patient__user'
        ).order_by('-appointment_date', '-appointment_time')


        cancelled_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='Cancelled',
            appointment_date__gte=last_week
        ).select_related('patient__user').order_by('-appointment_date', '-appointment_time')

        for appt in cancelled_appointments:
            if "\n\n[CANCEL_REASON]" in appt.reason_for_visit:
                parts = appt.reason_for_visit.split("\n\n[CANCEL_REASON]")
                appt.cancel_reason = parts[1]
            else:
                appt.cancel_reason = "No reason provided."

        cancelled_appointments_count = cancelled_appointments.count()

        context = {
            'doctor': doctor,
            'user': user,
            'total_patients': total_patients,
            'today_appointments': today_appointments,
            'today_appointments_count': today_appointments_count,
            'confirmed_today_count': confirmed_today_count,
            'pending_appointments': pending_appointments,
            'pending_appointments_count': pending_appointments_count,
            'upcoming_appointments': upcoming_appointments,
            'previous_appointments': previous_appointments,
            'completed_appointments': completed_appointments,
            'completed_appointments_count': completed_appointments_count,
            'cancelled_appointments': cancelled_appointments,
            'cancelled_appointments_count': cancelled_appointments_count,

            'all_patients': all_patients[:50],  # Limit to 50 for performance
        }
        
        return render(request, 'doctor/doctor_dashboard.html', context)
        
    except User.DoesNotExist:
        logger.error(f"User not found with ID {request.session.get('user_id')}")
        return redirect("login")
    except Exception as e:
        logger.error(f"Error in doctor dashboard: {str(e)}")
        return redirect("login")


def doctor_appointments(request):
    """
    View to show all appointments categorized by status
    """
    if request.session.get("role") != "Doctor":
        return redirect("login")

    try:
        user = User.objects.get(id=request.session["user_id"])
        doctor = Doctor.objects.filter(user=user).first()
        
        if not doctor:
            return redirect("login")
            
        if not doctor.is_approved:
            request.session.flush()
            return redirect("login")

        today = date.today()
        
        # Pending appointments
        pending_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='Pending'
        ).select_related('patient__user').order_by('appointment_date', 'appointment_time')

        # Upcoming appointments (Booked and future)
        upcoming_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='Booked',
            appointment_date__gte=today
        ).select_related('patient__user').order_by('appointment_date', 'appointment_time')

        # Completed appointments
        completed_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='Completed'
        ).select_related('patient__user').order_by('-appointment_date', '-appointment_time')

        # Cancelled appointments
        cancelled_appointments = Appointment.objects.filter(
            doctor=doctor,
            status='Cancelled'
        ).select_related('patient__user').order_by('-appointment_date', '-appointment_time')

        context = {
            'doctor': doctor,
            'pending_appointments': pending_appointments,
            'upcoming_appointments': upcoming_appointments,
            'completed_appointments': completed_appointments,
            'cancelled_appointments': cancelled_appointments,
            'pending_count': pending_appointments.count(),
            'upcoming_count': upcoming_appointments.count(),
            'completed_count': completed_appointments.count(),
            'cancelled_count': cancelled_appointments.count(),
        }

        return render(request, 'doctor/doctor_appointments.html', context)

    except Exception as e:
        logger.error(f"Error in doctor appointments view: {str(e)}")
        return redirect("doctor_dashboard")


def get_patient_details(request, patient_id):
    """
    API endpoint to get patient details
    """
    if request.session.get("role") != "Doctor":
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        patient = Patient.objects.select_related('user').get(id=patient_id)

        # Get latest appointment with this patient
        appointment = Appointment.objects.filter(
            patient=patient
        ).order_by('-appointment_date', '-appointment_time').first()

        patient_data = {
            'id': patient.id,
            'full_name': patient.user.full_name,
            'email': patient.user.email,
            'blood_group': patient.blood_group,
            'age': patient.age,
            'height_cm': patient.height_cm,
            'weight_kg': patient.weight_kg,
            'emergency_contact': patient.emergency_contact,
            # get reason from appointment
            'reason_for_visit': appointment.reason_for_visit if appointment else "N/A",
            'appointment_date': appointment.appointment_date.strftime("%d %b %Y") if appointment else "N/A",
            'appointment_time': appointment.appointment_time.strftime("%I:%M %p") if appointment else "N/A"

        }
        
        return JsonResponse({'success': True, 'patient': patient_data})
        
    except Patient.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Patient not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting patient details: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def approve_appointment(request, appointment_id):
    """
    Approve a pending appointment
    """
    if request.session.get("role") != "Doctor":
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        user = User.objects.get(id=request.session["user_id"])
        doctor = Doctor.objects.get(user=user)
        
        appointment = get_object_or_404(
            Appointment, 
            id=appointment_id, 
            doctor=doctor,
            status='Pending'
        )
        
        appointment.status = 'Booked'
        appointment.save()
        
        logger.info(f"Doctor {doctor.user.full_name} approved appointment {appointment_id}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Appointment approved successfully'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Doctor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Doctor not found'}, status=404)
    except Exception as e:
        logger.error(f"Error approving appointment: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def reject_appointment(request, appointment_id):
    """
    Reject a pending appointment
    """
    if request.session.get("role") != "Doctor":
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        user = User.objects.get(id=request.session["user_id"])
        doctor = Doctor.objects.get(user=user)
        
        appointment = get_object_or_404(
            Appointment, 
            id=appointment_id, 
            doctor=doctor,
            status='Pending'
        )
        
        # Get reason from request if provided
        data = json.loads(request.body)
        reason = data.get('reason', '')
        
        appointment.status = 'Cancelled'
        if reason:
            appointment.reason_for_visit = appointment.reason_for_visit + f"\n\n[CANCEL_REASON]{reason}"
        appointment.save()
        
        logger.info(f"Doctor {doctor.user.full_name} rejected appointment {appointment_id}")
        
        return JsonResponse({
            'success': True, 
            'message': 'Appointment rejected'
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Doctor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Doctor not found'}, status=404)
    except Exception as e:
        logger.error(f"Error rejecting appointment: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def mark_appointment_completed(request, appointment_id):
    """
    Mark an appointment as completed
    """
    if request.session.get("role") != "Doctor":
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        user = User.objects.get(id=request.session["user_id"])
        doctor = Doctor.objects.get(user=user)
        
        appointment = get_object_or_404(
            Appointment, 
            id=appointment_id, 
            doctor=doctor,
            status='Booked'
        )
        
        # Get notes from request if provided
        data = json.loads(request.body)
        notes = data.get('notes', '')
        
        appointment.status = 'Completed'
        appointment.notes = notes
        appointment.save()
        
        logger.info(f"Doctor {doctor.user.full_name} marked appointment {appointment_id} as completed")
        
        return JsonResponse({
            'success': True, 
            'message': 'Appointment marked as completed'
        })
        
    except Exception as e:
        logger.error(f"Error marking appointment as completed: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)



def doctor_patients(request):
    """
    Display a standalone page with all patients for the doctor.
    """
    if request.session.get("role") != "Doctor":
        return redirect('signin')
        
    try:
        user = User.objects.get(id=request.session["user_id"])
        doctor = Doctor.objects.get(user=user)
    except (User.DoesNotExist, Doctor.DoesNotExist):
        messages.error(request, "Access denied. Doctor profile not found.")
        return redirect('signin')
        
    if not doctor.is_approved:
        request.session.flush()
        return redirect("login")

    # Get all unique patients who have appointments with this doctor
    all_patients = Patient.objects.filter(
        appointment__doctor=doctor
    ).distinct()

    # Calculate pending appointments count for notification badge
    pending_appointments_count = Appointment.objects.filter(
        doctor=doctor,
        status='Pending'
    ).count()

    context = {
        'doctor': doctor,
        'all_patients': all_patients,
        'pending_appointments_count': pending_appointments_count,
    }
    
    return render(request, 'doctor/doctor_patients.html', context)
