import boto3
from app.core.config import get_settings

settings = get_settings()

_s3_client = None


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
    """Upload file to R2 and return public URL."""
    client = get_s3_client()
    client.put_object(
        Bucket=settings.r2_bucket_name,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return f"{settings.r2_public_url}/{key}"


def download_file_from_r2(key: str) -> bytes:
    """Download file from R2."""
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
