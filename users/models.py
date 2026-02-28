# users/models.py
from django.db import models

class User(models.Model):
    full_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    gender = models.CharField(max_length=10, null=True, blank=True)
    phone_number = models.CharField(max_length=15, unique=True)
    dob = models.DateField(null=True, blank=True)
    role = models.CharField(max_length=10)
    address = models.TextField(null=True, blank=True)  # ✅ ADD THIS
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "users"
        managed = False   

    def __str__(self):
        return self.full_name