from django.urls import path
from .views import doctor_page
from .views import doctor_dashboard, doctor_appointments, doctor_patients
from .views import get_patient_details
from .views import approve_appointment, reject_appointment

urlpatterns = [
    path("", doctor_page, name="doctor"),
    path("doctor_dashboard/", doctor_dashboard, name="doctor_dashboard"),
    path("appointments/", doctor_appointments, name="doctor_appointments"),
    path("patient-details/<int:patient_id>/", get_patient_details, name="patient_details"),
    path("appointment/<int:appointment_id>/approve/", approve_appointment, name="approve_appointment"),
    path("appointment/<int:appointment_id>/reject/", reject_appointment, name="reject_appointment"),
    path("patients/", doctor_patients, name="doctor_patients"),
]
