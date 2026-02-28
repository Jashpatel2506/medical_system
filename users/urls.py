from django.urls import path
from .views import login_view
from .views import signin_view
from .views import patient_page
from .views import doctor_page

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signin/", signin_view, name="signin"),
    path("patient/", patient_page, name="patient"),
    path("doctor/", doctor_page, name="doctor"),
    
]