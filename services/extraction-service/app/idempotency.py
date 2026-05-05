import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

TTL = 3600

_client = None

def get_client():
    global _client
    if _client is None:
        _client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _client

def is_duplicate(request_id: str) -> bool:
    key = f"extraction:{request_id}"  # change prefix per service
    result = get_client().set(key, "1", nx=True, ex=TTL)
    return result is None