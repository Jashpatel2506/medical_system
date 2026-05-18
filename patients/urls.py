# patients/urls.py
from django.urls import path
from .views import patient_page
from .views import chat_view, chat_api, patient_dashboard, book_appointment, all_doctors, download_report

urlpatterns = [
    path("", patient_page, name="patient_page"),
    path("dashboard/", patient_dashboard, name="patient_dashboard"),
    path("all-doctors/", all_doctors, name="all_doctors"),
    # Chat URLs
    path("chat/", chat_view, name='patient_chat'),
    path("api/chat/", chat_api, name='chat_api'),
    path("book-appointment/", book_appointment, name="book_appointment"),
    # Medical Report
    path("report/<int:report_id>/", download_report, name="download_report"),
]