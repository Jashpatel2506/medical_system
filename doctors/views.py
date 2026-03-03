# Create your views here.
from django.shortcuts import render, redirect
from doctors.models import Doctor
from users.models import User

def doctor_page(request):
    # 🔐 Role protection
    if request.session.get("role") != "Doctor":
        return redirect("login")

    user_id = request.session.get("user_id")
    user = User.objects.get(id=user_id)

    # ✅ create doctor row if not exists
    doctor, created = Doctor.objects.get_or_create(
        user=user,
        defaults={ "name": user.full_name }
    )

   

    if request.method == "POST":
        doctor.name = request.POST.get("name", doctor.name)
        doctor.age = request.POST.get("age")
        doctor.qualifications = request.POST.get("qualifications")
        doctor.specialization = request.POST.get("specialization")
        doctor.years_of_experience = request.POST.get("years_of_experience")
        doctor.clinic_name = request.POST.get("clinic_name")
        doctor.save()

        return redirect("doctor")


    return render(request, "doctor/doctor.html", {
        "doctor": doctor,
        "saved" : not created
    })
