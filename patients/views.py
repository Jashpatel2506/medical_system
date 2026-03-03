from django.shortcuts import render, redirect
from patients.models import Patient
from users.models import User

def patient_page(request):
    if request.session.get("role") != "Patient":
        return redirect("login")

    user_id = request.session.get("user_id")
    user = User.objects.get(id=user_id)

    # ✅ CREATE patient row if it doesn't exist
    patient, created = Patient.objects.get_or_create(
        user=user,
        defaults={  
        'blood_group': '',  
        'height_cm': 0,  
        'weight_kg': 0,   
        'emergency_contact': '',  
        'age': 0  
    }  
)

    if request.method == "POST":
        patient.blood_group = request.POST.get("blood_group")
        patient.height_cm = request.POST.get("height_cm")
        patient.weight_kg = request.POST.get("weight_kg")
        patient.emergency_contact = request.POST.get("emergency_contact")
        patient.age = request.POST.get("age")
        patient.save()

        return redirect("patient")

    return render(request, "patient/patient.html", {
        "patient": patient,
        "user": user,   # ✅ added
        "saved": request.method == "POST"
    })
