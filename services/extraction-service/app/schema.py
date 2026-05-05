from typing import Dict, Any


def normalize_fields(data: Dict[str, Any]) -> Dict[str, str]:
    """
    Ensures all expected fields exist and are strings
    """
    return {
        "name": str(data.get("name", "")).strip(),
        "dob": str(data.get("dob", "")).strip(),
        "id_number": str(data.get("id_number", "")).strip(),
    }


def build_output(request_id: str, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardized output for extraction service
    """
    normalized = normalize_fields(extracted_data)

    return {
        "request_id": request_id,
        "stage": "extracted",

        # 👇 core payload
        "extracted_data": normalized,

        # 👇 future-proof fields (very important)
        "meta": {
            "confidence": extracted_data.get("confidence", None),
            "raw_text": extracted_data.get("raw_text", None),
            "model": "layoutlm-docqa-v1"
        }
    }