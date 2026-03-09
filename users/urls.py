from django.urls import path
from .views import login_view
from .views import signin_view
from .views import logout_view

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signin/", signin_view, name="signin"),
    path('logout/', logout_view, name='logout'),
    
]