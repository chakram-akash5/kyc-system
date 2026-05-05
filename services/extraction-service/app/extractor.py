import os
import re
import logging
from pdf2image import convert_from_path
from PIL import Image
from app.utils import download_file
from app.ocr_utils import run_ocr_on_image

logger = logging.getLogger("extractor")


def extract_aadhaar(text: str) -> str:
    # Find all clean XXXX XXXX XXXX patterns and pick the first valid one
    matches = re.findall(r'\b(\d{4})\s(\d{4})\s(\d{4})\b', text)
    for m in matches:
        number = "".join(m)
        # Skip VID numbers (they appear after "VID :")
        vid_match = re.search(r'VID\s*[:\']?\s*(\d[\d\s]{10,})', text)
        if vid_match:
            vid = re.sub(r'\s', '', vid_match.group(1))
            if number == vid:
                continue
        return number
    # Fallback: plain 12 digits
    match = re.search(r'\b\d{12}\b', text)
    return match.group() if match else ""


def extract_pan(text: str) -> str:
    match = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', text)
    return match.group() if match else ""


def extract_id_number(text: str) -> str:
    aadhaar = extract_aadhaar(text)
    if aadhaar:
        return aadhaar
    return extract_pan(text)


def extract_dob(text: str) -> str:
    match = re.search(r'\b(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})\b', text)
    return match.group() if match else ""


def extract_name(text: str) -> str:
    BLACKLIST = [
        "INCOME", "TAX", "GOVERNMENT", "INDIA", "AUTHORITY",
        "DEPARTMENT", "AADHAAR", "UNIQUE", "PERMANENT", "S/O",
        "C/O", "DOB", "DATE", "MALE", "FEMALE", "ENROLLMENT",
        "ENROLMENT", "INFORMATION", "IDENTIFICATION", "SIGNATURE",
        "DISTRICT", "KOLKATA", "BENGAL", "JHARKHAND", "ADDRESS",
        "MOBILE", "STATE", "PIN", "CODE", "SUB", "VTC", "PO:"
    ]

    def is_valid_name(n: str) -> bool:
        n = n.strip()
        if not n or len(n) < 3 or len(n) > 50:
            return False
        if any(word in n.upper() for word in BLACKLIST):
            return False
        if any(char.isdigit() for char in n):
            return False
        words = n.split()
        if len(words) < 2:
            return False
        if not all(w[0].isupper() for w in words if w):
            return False
        return True

    def clean(n: str) -> str:
        return n.split('\n')[0].strip()

    # Pattern 1: After "Name" label (PAN card)
    match = re.search(r'(?:Name|NAME)\s*[:/]?\s*([A-Z][a-zA-Z\s]{2,40})', text)
    if match:
        name = clean(match.group(1))
        if is_valid_name(name):
            return name

    # Pattern 2: Name before DOB on card strip
    match = re.search(r'([A-Z][a-zA-Z\s]{2,40})\n[^\n]*(?:DOB\s*[:/]|जन्म\s*तिथि|Date\s*of\s*[Bb]irth)', text)
    if match:
        name = clean(match.group(1))
        if is_valid_name(name):
            return name

    # Pattern 3: After "To" (case-insensitive) within next 3 lines
    to_match = re.search(r'(?:^|\n)[Tt]o\s*\n((?:.*\n){0,3})', text)
    if to_match:
        block = to_match.group(1)
        for line in block.split('\n'):
            line = re.sub(r'^[^A-Z]+', '', line).strip()
            if re.match(r'^[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}$', line):
                if is_valid_name(line):
                    return line

    # Pattern 4: Scan every line for clean proper name
    for line in text.split('\n'):
        line = re.sub(r'^[^A-Z]+', '', line).strip()
        if re.match(r'^[A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}$', line):
            if is_valid_name(line):
                return line

    return ""


def extract_fields_from_text(text: str) -> dict:
    return {
        "name": extract_name(text),
        "dob": extract_dob(text),
        "id_number": extract_id_number(text),
    }


def extract_fields(document_url: str) -> dict:
    local_path = download_file(document_url)

    try:
        if local_path.lower().endswith(".pdf"):
            images = convert_from_path(local_path)
            full_text = ""
            for img in images:
                full_text += run_ocr_on_image(img) + "\n"
        else:
            image = Image.open(local_path)
            full_text = run_ocr_on_image(image)

        logger.info(f"[OCR RAW TEXT]\n{full_text}")
        return extract_fields_from_text(full_text)

    finally:
        try:
            os.remove(local_path)
        except Exception:
            pass