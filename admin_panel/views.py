from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from patients.models import Patient
from doctors.models import Doctor
from appointments.models import Appointment
from users.models import User

# Helper function to check if user is admin
def is_admin(request):
    return request.session.get('role') == 'Admin'

def admin_dashboard(request):
    if not is_admin(request):
        return redirect('login')
        
    today = timezone.now().date()
    total_patients = Patient.objects.count()
    total_doctors = Doctor.objects.count()
    total_appointments = Appointment.objects.count()
    total_medical_records = 0
    
    # Show only today's appointments
    recent_appointments = Appointment.objects.filter(appointment_date=today).order_by('appointment_time')
    
    completed_appointments = Appointment.objects.filter(status='Completed').count()
    confirmed_appointments = Appointment.objects.filter(status='Booked').count()
    pending_appointments = Appointment.objects.filter(status='Pending').count()
    missed_appointments = Appointment.objects.filter(status='Cancelled').count()
    
    # Weekly trend data (Last 7 days excluding today if you want trailing, or current week)
    # Let's do current week (Mon-Sun)
    start_of_week = today - timedelta(days=today.weekday())
    weekly_stats = []
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    
    max_appointments = 0
    for i in range(7):
        day_date = start_of_week + timedelta(days=i)
        count = Appointment.objects.filter(appointment_date=day_date).count()
        weekly_stats.append({
            'day': days[i],
            'count': count,
            'is_today': day_date == today
        })
        if count > max_appointments:
            max_appointments = count
            
    # Calculate height percentage for the chart
    for stat in weekly_stats:
        if max_appointments > 0:
            stat['height'] = (stat['count'] / max_appointments) * 100
        else:
            stat['height'] = 0

    pending_doctors = Doctor.objects.filter(is_approved=False)

    context = {
        'total_patients': total_patients,
        'total_doctors': total_doctors,
        'total_appointments': total_appointments,
        'total_medical_records': total_medical_records,
        'recent_appointments': recent_appointments,
        'completed_appointments': completed_appointments,
        'confirmed_appointments': confirmed_appointments,
        'pending_appointments': pending_appointments,
        'missed_appointments': missed_appointments,
        'weekly_stats': weekly_stats,
        'pending_doctors': pending_doctors,
    }
    return render(request, 'admin_panel/dashboard.html', context)

def admin_patients(request):
    if not is_admin(request):
        return redirect('login')
    patients = Patient.objects.all().select_related('user')
    return render(request, 'admin_panel/patients.html', {'patients': patients})

def admin_doctors(request):
    if not is_admin(request):
        return redirect('login')
    doctors = Doctor.objects.all().select_related('user')
    return render(request, 'admin_panel/doctors.html', {'doctors': doctors})

def admin_appointments(request):
    if not is_admin(request):
        return redirect('login')
    appointments = Appointment.objects.all().select_related('patient__user', 'doctor')
    return render(request, 'admin_panel/appointments.html', {'appointments': appointments})

def admin_medical_records(request):
    if not is_admin(request):
        return redirect('login')
    return render(request, 'admin_panel/medical_records.html', {})

def approve_doctor(request, doctor_id):
    if not is_admin(request):
        return redirect('login')
    if request.method == "POST":
        try:
            doctor = Doctor.objects.get(id=doctor_id)
            doctor.is_approved = True
            doctor.save()
        except Doctor.DoesNotExist:
            pass
    return redirect('admin_dashboard')
