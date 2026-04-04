from fastapi import APIRouter, Depends
from app.core.auth import get_current_user
from app.models.user import User
from app.services.storage import generate_presigned_url
import uuid

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("/presigned-url")
async def get_presigned_upload_url(
    filename: str = "scan.jpg",
    content_type: str = "image/jpeg",
    user: User = Depends(get_current_user),
):
    """
    Get a presigned URL for direct upload to R2 from the browser.
    Useful for large files — skips the backend server as middleman.
    """
    file_id = str(uuid.uuid4())
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "jpg"
    key = f"papers/{user.id}/{file_id}/original.{ext}"

    url = generate_presigned_url(key)

    return {
        "upload_url": url,
        "key": key,
        "file_id": file_id,
    }
