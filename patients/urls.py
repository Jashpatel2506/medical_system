# patients/urls.py
from django.urls import path
from .views import patient_page

urlpatterns = [
    path("", patient_page, name="patient"),
]