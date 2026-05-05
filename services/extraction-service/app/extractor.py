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
    # Pattern 1: After "To\n" (Aadhaar address block)
    match = re.search(r'(?:^|\n)To\s*\n([A-Z][a-zA-Z\s]{2,40})', text)
    if match:
        return match.group(1).strip()

    # Pattern 2: After "Name" label (PAN card)
    patterns = [
        r'(?:Name|NAME)\s*[:/]?\s*([A-Z][a-zA-Z\s]{2,40})',
        r'(?:नाम\s*/\s*Name)\s*([A-Z][a-zA-Z\s]{2,40})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            name = match.group(1).strip()
            if not any(word in name.upper() for word in [
                "INCOME", "TAX", "GOVERNMENT", "INDIA", "AUTHORITY",
                "DEPARTMENT", "AADHAAR", "UNIQUE", "PERMANENT"
            ]):
                return name

    # Pattern 3: Look for "Debam Das" style — two capitalized words on a line
    match = re.search(r'\n([A-Z][a-z]+\s[A-Z][a-z]+)\n', text)
    if match:
        return match.group(1).strip()

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