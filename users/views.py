from django.shortcuts import render, redirect
from .models import User
from patients.models import Patient
from doctors.models import Doctor
import re
from datetime import datetime, date
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings


def login_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        # ✅ HARDCODED ADMIN LOGIN
        if email == "admin@gmail.com" and password == "admin123":
            request.session["user_id"] = 0  # Special ID for hardcoded admin
            request.session["role"] = "Admin"
            request.session["full_name"] = "Administrator"
            return redirect("admin_dashboard")

        try:
            user = User.objects.get(email=email)

            # ✅ check plain text password
            if user.password == password: 
                if user.role == "Doctor":
                    try:
                        doctor = Doctor.objects.get(user=user)
                        if not doctor.is_approved:
                            return render(request, "login/login.html", {
                                "error": "Your account is pending admin approval."
                            })
                    except Doctor.DoesNotExist:
                        pass
                
                request.session["user_id"] = user.id
                request.session["role"] = user.role
                request.session["full_name"] = user.full_name   # ADD THIS

                if user.role == "Patient":
                    return redirect("patient_dashboard")
                elif user.role == "Doctor":
                    return redirect("doctor_dashboard")
                elif user.role == "Admin": # Support DB-based admin too
                    return redirect("admin_dashboard")

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
        confirm_password = request.POST.get("confirmPassword")
        role = request.POST.get("role")  # Patient or Doctor
        phone = request.POST.get("phone")
        address = request.POST.get("address")
        gender = request.POST.get("gender")
        dob_str = request.POST.get("dob")  

        # ✅ Password Validation
        if not password or len(password) < 8:
            return render(request, "login/signin.html", {"error": "Password must be at least 8 characters long and contain at least one letter, one number, and one special character"})
        
        if password != confirm_password:
            return render(request, "login/signin.html", {"error": "Passwords do not match"})
            
        # Password complexity: at least one letter, one number, and one special character
        if not (re.search(r"[A-Za-z]", password) and re.search(r"[0-9]", password) and re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
            return render(request, "login/signin.html", {"error": "Password must be at least 8 characters long and contain at least one letter, one number, and one special character"})

        # ✅ Age Validation (18+)
        if dob_str:
            try:
                dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                today = date.today()
                age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
                if age < 18:
                    return render(request, "login/signin.html", {"error": "You must be at least 18 years old to register"})
            except ValueError:
                return render(request, "login/signin.html", {"error": "Invalid date of birth format"})
        else:
            return render(request, "login/signin.html", {"error": "Date of birth is required"})

        

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
            return redirect("patient_page")
            
        elif role == "Doctor":
            cert_file = request.FILES.get('certificate_file')
            lic_file = request.FILES.get('license_file')
            today = date.today()
            age = 0
            if dob:
                 age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            Doctor.objects.create(
                user=user,
                name=user.full_name,
                age=age,
                certificate_file=cert_file,
                license_file=lic_file,
                is_approved=False
            )
            # Log them in temporarily so they can fill their profile info
            request.session["user_id"] = user.id
            request.session["role"] = user.role
            request.session["full_name"] = user.full_name
            return redirect("doctor")

        # ✅ after registration → go to login
        return redirect("login")

    # Calculate 18 years ago for the date picker max attribute
    today = date.today()
    eighteen_years_ago = date(today.year - 18, today.month, today.day).strftime('%Y-%m-%d')
    return render(request, 'login/signin.html', {'eighteen_years_ago': eighteen_years_ago})

def logout_view(request):
    request.session.flush()  # clears everything
    return redirect("login")

def forgot_password_view(request):
    if request.method == "POST":
        email = request.POST.get("email")
        try:
            user = User.objects.get(email=email)
            signer = TimestampSigner()
            token = signer.sign(user.email)
            reset_url = request.build_absolute_uri(reverse('reset_password', args=[token]))
            
            # Send Email
            subject = "HealSmart - Password Reset Request"
            message = f"Hello {user.full_name},\n\nPlease click the link below to reset your password. This link is valid for 1 hour.\n\n{reset_url}\n\nIf you did not request this, please ignore this email."
            
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                return render(request, "login/forgot_password.html", {
                    "success_msg": "Password reset link has been sent to your email address."
                })
            except Exception as e:
                # If email fails, log error and show failure. In dev with no SMTP it logs here.
                print(f"Error sending email: {e}")
                print(f"--- RESET LINK (For Testing) ---\n{reset_url}\n-------------------------------")
                return render(request, "login/forgot_password.html", {
                    "error": "Failed to send email. Check configuration or logs."
                })
                
        except User.DoesNotExist:
            # Prevent email enumeration by still showing success or generic message
            return render(request, "login/forgot_password.html", {
                "success_msg": "If the email is registered, a reset link has been sent."
            })
            
    return render(request, "login/forgot_password.html")

def reset_password_view(request, token):
    signer = TimestampSigner()
    try:
        # Token is valid for 1 hour (3600 seconds)
        email = signer.unsign(token, max_age=3600)
    except SignatureExpired:
        return render(request, "login/reset_password.html", {"error": "The reset link has expired. Please request a new one.", "invalid_link": True})
    except BadSignature:
        return render(request, "login/reset_password.html", {"error": "Invalid reset link.", "invalid_link": True})
        
    if request.method == "POST":
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirmPassword")
        
        if not password or len(password) < 8:
            return render(request, "login/reset_password.html", {"error": "Password must be at least 8 characters long and contain at least one letter, one number, and one special character"})
            
        if password != confirm_password:
            return render(request, "login/reset_password.html", {"error": "Passwords do not match"})
            
        if not (re.search(r"[A-Za-z]", password) and re.search(r"[0-9]", password) and re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
            return render(request, "login/reset_password.html", {"error": "Password must be at least 8 characters long and contain at least one letter, one number, and one special character"})
            
        try:
            user = User.objects.get(email=email)
            user.password = password  # Note: continuing to use plain text password as per current project design
            user.save()
            return render(request, "login/login.html", {"success_msg": "Your password has been successfully reset. You can now log in."})
        except User.DoesNotExist:
            return render(request, "login/reset_password.html", {"error": "User no longer exists.", "invalid_link": True})
            
    return render(request, "login/reset_password.html", {"email": email})
