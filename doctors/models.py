# doctors/models.py
from django.db import models
from users.models import User
class Doctor(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        db_column="user_id"
    )
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=150, null=True, blank=True)
    qualifications = models.TextField(null=True, blank=True)
    years_of_experience = models.IntegerField(null=True, blank=True)
    clinic_name = models.CharField(max_length=150, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "doctors"
        managed = False

    def __str__(self):
        return f"Doctor: {self.name}"