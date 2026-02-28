from django.shortcuts import render, redirect
from .models import User
from patients.models import Patient


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            user = User.objects.get(email=email)

            # ✅ check plain text password
            if user.password == password: 
                request.session["user_id"] = user.id
                request.session["role"] = user.role
                request.session["full_name"] = user.full_name   # ADD THIS

                if user.role == "Patient":
                    return redirect("patient")
                elif user.role == "Doctor":
                    return redirect("doctor")

            else:
                return render(request, "login/login.html", {
                    "error": "Invalid email or password"
                })

        except User.DoesNotExist:
            return render(request, "login/login.html", {
                "error": "user does not exist"
            })

    return render(request, "login/login.html")

def signin_view(request):      
    if request.method == "POST":
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        password = request.POST.get("password")
        role = request.POST.get("role")  # Patient or Doctor
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        gender = request.POST.get("gender")   # ✅ ADD
        dob = request.POST.get("dob")  

        # ❌ check if email already exists
        if User.objects.filter(email=email).exists():
            return render(request, "login/signin.html", {
                "error": "Email already registered"
            })

        # ✅ save to PostgreSQL
        User.objects.create(
            full_name=full_name,
            email=email,
            password=password,   # (plain text for now)
            role=role,
            phone_number=phone,
            gender=gender,           # ✅ SAVED
            dob=dob or None
        )
        # ✅ CREATE PATIENT ROW ONLY IF ROLE IS PATIENT
        if role == "Patient":
            Patient.objects.create(user=user)

        # ✅ after registration → go to login
        return redirect("login")

    return render(request, 'login/signin.html')

def patient_page(request):
    if request.session.get("role") != "Patient":
        return redirect("login")
    return render(request, 'patient/patient.html')

def doctor_page(request):
    if request.session.get("role") != "Doctor":
        return redirect("login")
    return render(request, 'doctor/doctor.html')
