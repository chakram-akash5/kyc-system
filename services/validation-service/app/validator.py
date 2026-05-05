import re
from datetime import datetime, date


def calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - (
        (today.month, today.day) < (dob.month, dob.day)
    )


def validate(data: dict):
    errors = []

    # DOB validation
    dob_str = data.get("dob")
    if not dob_str:
        errors.append("DOB missing")
    else:
        try:
            dob = datetime.strptime(dob_str, "%d/%m/%Y").date()
            age = calculate_age(dob)

            if age < 18:
                errors.append("Underage")
            if age > 120:
                errors.append("Invalid age")

        except Exception:
            errors.append("Invalid DOB format")

    # Aadhaar validation
    id_num = data.get("id_number")
    if not re.match(r"^\d{12}$", id_num or ""):
        errors.append("Invalid Aadhaar")

    # Name validation
    name = data.get("name")
    if not name or len(name.strip()) < 3:
        errors.append("Invalid name")

    return errors