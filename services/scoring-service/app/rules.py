import re
from datetime import datetime


def parse_dob(dob: str):
    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d/%m/%y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dob.strip(), fmt)
        except ValueError:
            continue
    return None


def evaluate_age(dob: str):
    dt = parse_dob(dob)

    if dt is None:
        return ("unknown", 25)

    age = (datetime.now() - dt).days // 365

    if age < 18:
        return ("high", 40)
    elif age < 21:
        return ("medium", 20)
    elif age > 90:
        return ("medium", 15)
    else:
        return ("low", 0)


def evaluate_name(name: str):
    if not name or len(name) < 3:
        return ("bad", 30)

    if any(char.isdigit() for char in name):
        return ("suspicious", 25)

    return ("good", 0)


def evaluate_id(id_number: str):
    if not id_number:
        return ("invalid", 40)

    digits_only = re.sub(r'\s', '', id_number)

    if digits_only.isdigit() and len(digits_only) == 12:
        return ("valid", 0)

    if re.fullmatch(r'[A-Z]{5}[0-9]{4}[A-Z]', id_number.strip().upper()):
        return ("valid", 0)

    return ("invalid", 40)