from django.http import HttpResponse
from django.shortcuts import render

def home(request):
    #return HttpResponse("Hello, World!. you are at django ")
    return render(request, 'home1.html')

from django.http import HttpResponse
from django.shortcuts import render

def home(request):
    #return HttpResponse("Hello, World!. you are at django ")
    return render(request, 'home1.html')

def login(request):
    return render(request, 'login/login.html')

def signin(request):
    return render(request, 'login/signin.html')   

def patient(request):
    return render(request, 'patient/patient.html')

def doctor(request):
    return render(request, 'doctor/doctor.html')


def contact(request):
    return render(request, 'contact.html')