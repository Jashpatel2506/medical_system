from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('patients/', views.admin_patients, name='admin_patients'),
    path('doctors/', views.admin_doctors, name='admin_doctors'),
    path('appointments/', views.admin_appointments, name='admin_appointments'),
    path('medical-records/', views.admin_medical_records, name='admin_medical_records'),
    path('approve_doctor/<int:doctor_id>/', views.approve_doctor, name='approve_doctor'),
]
