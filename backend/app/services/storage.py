import boto3
import os
import logging
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_s3_client = None

# Local storage fallback path
LOCAL_STORAGE_PATH = "/tmp/classpal-papers"


def is_r2_configured() -> bool:
    return bool(settings.r2_access_key_id and settings.r2_secret_access_key and settings.r2_endpoint_url)


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=settings.r2_endpoint_url,
            aws_access_key_id=settings.r2_access_key_id,
            aws_secret_access_key=settings.r2_secret_access_key,
            region_name="auto",
        )
    return _s3_client


async def upload_file_to_r2(
    file_bytes: bytes, key: str, content_type: str
) -> str:
    """Upload file to R2 or local fallback. Returns URL."""
    if not is_r2_configured():
        # Local fallback for testing
        local_path = os.path.join(LOCAL_STORAGE_PATH, key)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        logger.info(f"Saved locally: {local_path} ({len(file_bytes)} bytes)")
        return f"/local-files/{key}"

    client = get_s3_client()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"{settings.r2_public_url}/{key}"


def download_file_from_r2(key: str) -> bytes:
    """Download file from R2 or local fallback."""
    if not is_r2_configured():
        local_path = os.path.join(LOCAL_STORAGE_PATH, key)
        if os.path.exists(local_path):
            with open(local_path, "rb") as f:
                return f.read()
        raise FileNotFoundError(f"Local file not found: {local_path}")

    client = get_s3_client()
    response = client.get_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
    )
    return response["Body"].read()


def generate_presigned_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for direct upload."""
    client = get_s3_client()
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.r2_bucket_name,
            "Key": key,
        },
        ExpiresIn=expires_in,
    )
