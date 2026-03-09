# patients/urls.py
from django.urls import path
from .views import patient_page
from .views import chat_view, chat_api

urlpatterns = [
    path("", patient_page, name="patient_page"),
    # Chat URLs
    path("chat/", chat_view, name='patient_chat'),
    path("api/chat/", chat_api, name='chat_api'),
]