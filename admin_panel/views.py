from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from patients.models import Patient
from doctors.models import Doctor
from appointments.models import Appointment
from users.models import User

# @login_required(login_url='login')  # Uncomment when ready to enforce login
def admin_dashboard(request):
    total_patients = Patient.objects.count()
    total_doctors = Doctor.objects.count()
    total_appointments = Appointment.objects.count()
    # No MedicalRecord model, using 0 for now or placeholder
    total_medical_records = 0
    
    recent_appointments = Appointment.objects.all().order_by('-appointment_date', '-appointment_time')[:5]
    
    # Counts for appointment status chart
    completed_appointments = Appointment.objects.filter(status='Completed').count()
    confirmed_appointments = Appointment.objects.filter(status='Booked').count()
    pending_appointments = Appointment.objects.filter(status='Pending').count()
    missed_appointments = Appointment.objects.filter(status='Cancelled').count()
    
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
    }
    return render(request, 'admin_panel/dashboard.html', context)

# @login_required(login_url='login')
def admin_patients(request):
    patients = Patient.objects.all().select_related('user')
    return render(request, 'admin_panel/patients.html', {'patients': patients})

# @login_required(login_url='login')
def admin_doctors(request):
    doctors = Doctor.objects.all().select_related('user')
    return render(request, 'admin_panel/doctors.html', {'doctors': doctors})

# @login_required(login_url='login')
def admin_appointments(request):
    appointments = Appointment.objects.all().select_related('patient__user', 'doctor')
    return render(request, 'admin_panel/appointments.html', {'appointments': appointments})

# @login_required(login_url='login')
def admin_medical_records(request):
    # Placeholder
    return render(request, 'admin_panel/medical_records.html', {})

