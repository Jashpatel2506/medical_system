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