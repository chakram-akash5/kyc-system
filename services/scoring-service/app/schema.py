def build_output(request_id, score, level, signals):
    return {
        "request_id": request_id,
        "stage": "scored",
        "risk_score": score,
        "risk_level": level,
        "signals": signals
    }