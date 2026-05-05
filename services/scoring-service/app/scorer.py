from app.rules import evaluate_age, evaluate_name, evaluate_id


def compute_score(data: dict):
    signals = {}
    total_score = 0

    # Age
    age_risk, age_score = evaluate_age(data.get("dob", ""))
    signals["age_risk"] = age_risk
    total_score += age_score

    # Name
    name_quality, name_score = evaluate_name(data.get("name", ""))
    signals["name_quality"] = name_quality
    total_score += name_score

    # ID
    id_status, id_score = evaluate_id(data.get("id_number", ""))
    signals["id_validity"] = id_status
    total_score += id_score

    return total_score, signals


def get_risk_level(score: int):
    if score < 20:
        return "LOW"
    elif score < 50:
        return "MEDIUM"
    else:
        return "HIGH"