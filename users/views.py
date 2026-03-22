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
                    return redirect("patient_dashboard")
                elif user.role == "Doctor":
                    return redirect("doctor_dashboard")

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
        # ❌ check if phone number has at least 10 digits
        if not phone or len(phone) < 10:
            return render(request, "login/signin.html", {
                "error": "Phone number must be at least 10 digits"
            })

        # ✅ Check if phone already exists
        if User.objects.filter(phone_number=phone).exists():
            return render(request, "login/signin.html", {
                "error": "Phone number already registered"
            })

        # ✅ save to PostgreSQL
        user = User.objects.create(
            full_name=full_name,
            email=email,
            password=password,   # (plain text for now)
            role=role,
            phone_number=phone,
            gender=gender,           # ✅ SAVED
            dob=dob or None,
            address=address
        )
        # ✅ CREATE PATIENT ROW ONLY IF ROLE IS PATIENT
        if role == "Patient":
            Patient.objects.create(
                user=user,
                blood_group='',
                height_cm=0,
                weight_kg=0,
                emergency_contact='',
                age=0
            )
            # ✅ set session and redirect by role
        request.session["user_id"] = user.id
        request.session["role"] = user.role
        request.session["full_name"] = user.full_name

        if role == "Patient":
            return redirect("patient_page")
        elif role == "Doctor":
            return redirect("doctor")

        # ✅ after registration → go to login
        return redirect("login")

    return render(request, 'login/signin.html')

def logout_view(request):
    request.session.flush()  # clears everything
    return redirect("login")



