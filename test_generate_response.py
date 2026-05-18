import os
import django
import sys
from django.conf import settings

sys.path.append(r"d:\final year project\medical_system")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medical_system.settings")
try:
    django.setup()
except Exception as e:
    print("Django setup failed", e)

from patients.views import generate_response
from users.models import User
from patients.models import Patient

class MockSession(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modified = False

class MockRequest:
    def __init__(self):
        self.session = MockSession()

msg = "predict"
request = MockRequest()
request.session['chat_symptoms'] = ["headache", "fever", "cough", "fatigue"]
try:
    user = User.objects.first()
    patient = Patient.objects.first()
    if not patient and user:
        patient = Patient(user=user)

    print("Testing generate_response...")
    result = generate_response(msg, request, patient)
    print("SUCCESS:")
    print(str(result)[:200])
except Exception as e:
    import traceback
    print("FAILED:")
    traceback.print_exc()

