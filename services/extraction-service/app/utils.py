import os
import tempfile
import boto3
import requests
from urllib.parse import urlparse

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://localstack:4566")
S3_BUCKET = os.getenv("S3_BUCKET", "kyc-documents")

s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    region_name="us-east-1",
    aws_access_key_id="test",
    aws_secret_access_key="test",
)

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}


def download_file(url: str) -> str:
    parsed = urlparse(url)
    ext = os.path.splitext(parsed.path)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        ext = ".jpg"

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)

    # S3 path: /bucket-name/key
    if "localstack" in url or parsed.scheme == "s3":
        # Extract bucket and key from URL
        # URL format: http://localstack:4566/kyc-documents/uploads/request-id.jpg
        path_parts = parsed.path.lstrip("/").split("/", 1)
        bucket = path_parts[0]
        key = path_parts[1]

        s3.download_fileobj(bucket, key, tmp)
    else:
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        for chunk in response.iter_content(8192):
            tmp.write(chunk)

    tmp.close()
    return tmp.name