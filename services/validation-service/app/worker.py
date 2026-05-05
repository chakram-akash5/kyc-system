import os
import json
import time
import logging
import boto3
from app.validator import validate
from app.idempotency import is_duplicate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("validation-worker")

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
    try:
        body = json.loads(msg["Body"])
    except Exception:
        logger.error("[VALIDATION] Bad JSON → DLQ")
        send_to_dlq({"error": "invalid_json"}, dlq_url)
        return

    if body.get("stage") != "extracted":
        logger.warning(f"[VALIDATION] Unexpected stage: {body.get('stage')} — skipping")
        return

    request_id = body.get("request_id")

    if is_duplicate(request_id):
        logger.info(f"[VALIDATION] Duplicate skipped {request_id}")
        return

    retry = body.get("retry_count", 0)

    try:
        errors = validate(body["extracted_data"])

        result = {
            "request_id": request_id,
            "stage": "validated",
            "is_valid": len(errors) == 0,
            "errors": errors,
            "extracted_data": body["extracted_data"]
        }

        sqs.send_message(
            QueueUrl=output_url,
            MessageBody=json.dumps(result)
        )

        logger.info(f"[VALIDATION] Success {request_id}")

    except Exception as e:
        logger.error(f"[VALIDATION] Fail {request_id}: {str(e)}")

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

        except Exception as e:
            logger.error(f"[VALIDATION] Poll error: {str(e)}")
            time.sleep(5)


if __name__ == "__main__":
    poll()