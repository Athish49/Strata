import boto3
from botocore.config import Config
from app.config import settings


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_to_r2(key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    client = get_r2_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def get_r2_object(key: str) -> bytes:
    client = get_r2_client()
    response = client.get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    return response["Body"].read()
