# Create your models here.
from django.db import models
from patients.models import Patient
from doctors.models import Doctor

class Appointment(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Booked', 'Booked'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)

    appointment_date = models.DateField()
    appointment_time = models.TimeField()

    reason_for_visit = models.TextField()

    status = models.CharField(
        max_length=20,
        default="Pending"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appointments"   # your existing table name

    def __str__(self):
        return f"{self.patient} - {self.doctor} - {self.appointment_date}"


class MedicalReport(models.Model):
    """Stores the AI disease prediction report for each patient session."""
    patient             = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_reports')
    appointment         = models.ForeignKey(Appointment, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports')
    symptoms            = models.TextField()               # comma-separated matched symptoms
    predicted_disease   = models.CharField(max_length=200)
    disease_description = models.TextField(blank=True)
    precautions         = models.TextField(blank=True)  
    diet_plan           = models.TextField(blank=True, default="")# stored as JSON list string
    confidence          = models.FloatField(default=0.0)
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "medical_reports"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.patient} — {self.predicted_disease} ({self.created_at.date()})"