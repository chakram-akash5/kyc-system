import os
import json
import time
import logging
import boto3
import redis as redis_lib
from botocore.exceptions import EndpointConnectionError

from app.extractor import extract_fields
from app.schema import build_output
from app.idempotency import is_duplicate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("extraction-worker")

SQS_ENDPOINT = "http://localstack:4566"
REGION = "us-east-1"

INPUT_QUEUE = os.getenv("INPUT_QUEUE")
OUTPUT_QUEUE = os.getenv("OUTPUT_QUEUE")
DLQ_QUEUE = os.getenv("DLQ_QUEUE")

MAX_RETRIES = 3

sqs = boto3.client(
    "sqs",
    endpoint_url=SQS_ENDPOINT,
    region_name=REGION,
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

_redis_client = None


def get_redis():
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_lib.Redis(
            host=os.getenv("REDIS_HOST", "redis"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True
        )
    return _redis_client


def wait_for_queue(name, retries=15):
    for _ in range(retries):
        try:
            return sqs.get_queue_url(QueueName=name)["QueueUrl"]
        except:
            time.sleep(2)
    raise Exception(f"{name} not ready")


def send_to_dlq(body, dlq_url):
    sqs.send_message(QueueUrl=dlq_url, MessageBody=json.dumps(body))


def process_message(message, input_url, output_url, dlq_url):
    try:
        body = json.loads(message["Body"])
    except:
        logger.error("[EXTRACTION] Bad JSON → DLQ")
        send_to_dlq({"error": "invalid_json"}, dlq_url)
        return

    retry = body.get("retry_count", 0)
    request_id = body.get("request_id")

    if is_duplicate(request_id):
        logger.info(f"[EXTRACTION] Duplicate skipped {request_id}")
        return

    document_url = body.get("document_url")

    if not document_url:
        logger.error("[EXTRACTION] Missing document_url → DLQ")
        send_to_dlq(body, dlq_url)
        return

    try:
        extracted = extract_fields(document_url)
        output = build_output(request_id, extracted)

        sqs.send_message(QueueUrl=output_url, MessageBody=json.dumps(output))

        # Store extracted fields in Redis for inspection
        get_redis().set(
            f"kyc:extracted:{request_id}",
            json.dumps(output["extracted_data"]),
            ex=86400
        )

        logger.info(f"[EXTRACTION] Success {request_id}")

    except Exception as e:
        logger.error(f"[EXTRACTION] Fail {request_id}: {str(e)}")

        if retry >= MAX_RETRIES:
            send_to_dlq(body, dlq_url)
        else:
            body["retry_count"] = retry + 1
            sqs.send_message(QueueUrl=input_url, MessageBody=json.dumps(body))


def poll():
    input_url = wait_for_queue(INPUT_QUEUE)
    output_url = wait_for_queue(OUTPUT_QUEUE)
    dlq_url = wait_for_queue(DLQ_QUEUE)

    while True:
        try:
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

        except EndpointConnectionError:
            time.sleep(5)


if __name__ == "__main__":
    poll()