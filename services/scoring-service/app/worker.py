import os
import json
import time
import logging
import boto3
import redis
from app.scorer import compute_score, get_risk_level
from app.schema import build_output
from app.idempotency import is_duplicate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scoring-worker")

INPUT_QUEUE = os.getenv("INPUT_QUEUE")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE")
DLQ_QUEUE = os.getenv("DLQ_QUEUE")

MAX_RETRIES = 3

sqs = boto3.client(
    "sqs",
    endpoint_url="http://localstack:4566",
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)


def wait_for_queue(name):
    for _ in range(15):
        try:
            return sqs.get_queue_url(QueueName=name)["QueueUrl"]
        except:
            time.sleep(2)
    raise Exception(f"{name} not ready")


def send_to_dlq(body, dlq_url):
    sqs.send_message(QueueUrl=dlq_url, MessageBody=json.dumps(body))


def process_message(msg, input_url, output_url, dlq_url):
    body = json.loads(msg["Body"])

    if body.get("stage") != "validated":
        return

    request_id = body.get("request_id")

    if is_duplicate(request_id):
        logger.info(f"[SCORING] Duplicate skipped {request_id}")
        return

    retry = body.get("retry_count", 0)

    try:
        score, signals = compute_score(body.get("extracted_data", {}))
        level = get_risk_level(score)

        output = build_output(request_id, score, level, signals)

        sqs.send_message(
            QueueUrl=output_url,
            MessageBody=json.dumps(output)
        )

        redis_client.set(
            f"kyc:result:{request_id}",
            json.dumps(output),
            ex=86400  # TTL: 24 hours
        )

        logger.info(f"[SCORING] Success {request_id}")

    except Exception as e:
        logger.error(f"[SCORING] Fail {request_id}: {str(e)}")

        if retry >= MAX_RETRIES:
            send_to_dlq(body, dlq_url)
        else:
            body["retry_count"] = retry + 1
            sqs.send_message(
                QueueUrl=input_url,
                MessageBody=json.dumps(body)
            )


def poll():
    input_url = wait_for_queue(INPUT_QUEUE)
    output_url = wait_for_queue(OUTPUT_QUEUE)
    dlq_url = wait_for_queue(DLQ_QUEUE)

    while True:
        resp = sqs.receive_message(
            QueueUrl=input_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=10
        )

        for msg in resp.get("Messages", []):
            process_message(msg, input_url, output_url, dlq_url)

            sqs.delete_message(
                QueueUrl=input_url,
                ReceiptHandle=msg["ReceiptHandle"]
            )


if __name__ == "__main__":
    poll()