from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
import boto3
import redis
import json
import uuid
import os
import time

app = FastAPI()

# Config
SQS_ENDPOINT = os.getenv("SQS_ENDPOINT", "http://localstack:4566")
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localstack:4566")
QUEUE_NAME = os.getenv("INPUT_QUEUE", "kyc-raw-queue")
S3_BUCKET = os.getenv("S3_BUCKET", "kyc-documents")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}

sqs = boto3.client(
    "sqs",
    endpoint_url=SQS_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    decode_responses=True
)

queue_url = None


def wait_for_queue(retries=10, delay=2):
    global queue_url
    for _ in range(retries):
        try:
            queue_url = sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
            print(f"[GATEWAY] Connected to queue: {QUEUE_NAME}")
            return
        except Exception:
            time.sleep(delay)
    raise Exception("Queue not ready")


@app.on_event("startup")
def startup():
    wait_for_queue()


class KYCRequest(BaseModel):
    document_url: str


@app.post("/kyc")
def submit_kyc(request: KYCRequest):
    try:
        request_id = str(uuid.uuid4())

        payload = {
            "request_id": request_id,
            "document_url": request.document_url
        }

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload)
        )

        return {"status": "submitted", "request_id": request_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/kyc/upload")
def upload_kyc(file: UploadFile = File(...)):
    try:
        # Validate extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}"
            )

        request_id = str(uuid.uuid4())
        s3_key = f"uploads/{request_id}{ext}"

        # Upload to S3
        s3.upload_fileobj(
            file.file,
            S3_BUCKET,
            s3_key,
            ExtraArgs={"ContentType": file.content_type}
        )

        # S3 URL accessible within Docker network
        document_url = f"http://localstack:4566/{S3_BUCKET}/{s3_key}"

        payload = {
            "request_id": request_id,
            "document_url": document_url
        }

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(payload)
        )

        return {"status": "submitted", "request_id": request_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/kyc/{request_id}/result")
def get_result(request_id: str):
    try:
        data = redis_client.get(f"kyc:result:{request_id}")

        if not data:
            raise HTTPException(
                status_code=404,
                detail="Result not found or still processing"
            )

        return json.loads(data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/kyc/{request_id}/extracted")
def get_extracted(request_id: str):
    try:
        data = redis_client.get(f"kyc:extracted:{request_id}")

        if not data:
            raise HTTPException(
                status_code=404,
                detail="Extracted data not found or still processing"
            )

        return json.loads(data)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))