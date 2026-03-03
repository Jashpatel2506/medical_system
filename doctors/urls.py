from django.urls import path
from .views import doctor_page

urlpatterns = [
    path("", doctor_page, name="doctor"),
]