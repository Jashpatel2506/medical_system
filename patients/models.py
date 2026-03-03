# Create your models here.
from django.db import models
from users.models import User

class Patient(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        db_column="user_id"
    )
    blood_group = models.CharField(max_length=5)
    height_cm = models.IntegerField()
    weight_kg = models.IntegerField()
    emergency_contact = models.CharField(max_length=15)
    age = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)  # ✅ FIX


    class Meta:
        db_table = "patients"   # ✅ EXISTING TABLE
        managed = False         # 🚨 VERY IMPORTANT

    def __str__(self):
        return f"Patient: {self.user.full_name}"
