from django.urls import path
from .views import login_view, signin_view, logout_view, forgot_password_view, reset_password_view

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signin/", signin_view, name="signin"),
    path('logout/', logout_view, name='logout'),
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("reset-password/<str:token>/", reset_password_view, name="reset_password"),
]