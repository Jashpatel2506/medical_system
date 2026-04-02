import re
from datetime import datetime, date

def validate_password(password, confirm_password):
    if not password or len(password) < 8:
        return "Password must be at least 8 characters long"
    if password != confirm_password:
        return "Passwords do not match"
    if not (re.search(r"[A-Za-z]", password) and re.search(r"[0-9]", password) and re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
        return "Password must contain at least one letter, one number, and one special character"
    return "Valid"

def validate_age(dob_str):
    try:
        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            return "You must be at least 18 years old to register"
        return "Valid"
    except ValueError:
        return "Invalid date of birth format"

# Test cases
print(f"Short password: {validate_password('abc', 'abc')}")
print(f"Mismatched passwords: {validate_password('Password123!', 'Password123')}")
print(f"No number: {validate_password('Password!', 'Password!')}")
print(f"No special: {validate_password('Password123', 'Password123')}")
print(f"Valid: {validate_password('Password123!', 'Password123!')}")

print(f"Under 18 (2010): {validate_age('2010-01-01')}")
print(f"Exactly 18 (2008-03-28): {validate_age('2008-03-28')}") # Today is 2026-03-28
print(f"Over 18 (2000): {validate_age('2000-01-01')}")
