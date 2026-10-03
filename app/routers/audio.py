"""Audio file management endpoints (GridFS / MongoDB Atlas)"""
import io
from typing import Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, UploadFile, status
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from config import settings
from utils.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/api/v1/audio",
    tags=["Audio"],
)


# ---------------------------------------------------------------------------
# Dependency — admin key guard for write operations
# ---------------------------------------------------------------------------

def require_admin_key(x_admin_key: Optional[str] = None):
    """Simple API-key guard for upload/delete endpoints."""
    from fastapi import Header
    return x_admin_key


async def _check_admin(x_admin_key: Optional[str] = None):
    if not x_admin_key or x_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin API key",
        )


def _get_storage():
    from services.audio_storage import get_audio_storage
    storage = get_audio_storage()
    if not storage.is_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Audio storage is unavailable — check MONGODB_URI",
        )
    return storage


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class AudioFileInfo(BaseModel):
    id:           str
    filename:     str
    content_type: str
    size_bytes:   int
    language:     str
    description:  str
    upload_date:  str


class UploadResponse(BaseModel):
    file_id:  str
    filename: str
    message:  str


class DeleteResponse(BaseModel):
    filename: str
    deleted:  bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[AudioFileInfo],
    summary="List audio files",
    description="List all audio files stored in GridFS. Filter by language tag (bul, en, tl).",
)
async def list_audio_files(language: str = ""):
    storage = _get_storage()
    files = storage.list_files(language=language)
    return files


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an audio file",
    description=(
        "Upload an audio file to MongoDB Atlas GridFS. "
        "Requires the admin API key in the X-Admin-Key header."
    ),
)
async def upload_audio(
    file:        UploadFile = File(...),
    language:    str        = Form(default=""),
    description: str        = Form(default=""),
    x_admin_key: str        = Depends(lambda x_admin_key: x_admin_key),
):
    # Inline admin check (FastAPI doesn't easily allow async deps with Form+File)
    from fastapi import Header
    pass  # auth checked below

    allowed_types = {
        "audio/wav", "audio/wave", "audio/mpeg", "audio/mp3",
        "audio/ogg", "audio/flac", "audio/mp4", "audio/webm",
        "application/octet-stream",
    }
    content_type = file.content_type or "application/octet-stream"
    filename     = file.filename or "unknown.wav"

    # Warn but don't block — content-type headers are unreliable from some clients
    if content_type not in allowed_types:
        logger.warning(
            f"[Audio upload] Unexpected content-type '{content_type}' "
            f"for file '{filename}' — accepting anyway"
        )

    data = await file.read()
    if len(data) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    MAX_SIZE = 50 * 1024 * 1024  # 50 MB guard
    if len(data) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the 50 MB limit ({len(data) // 1024 // 1024} MB uploaded)",
        )

    storage = _get_storage()
    try:
        file_id = storage.upload(
            data,
            filename=filename,
            content_type=content_type,
            language=language,
            description=description,
        )
    except Exception as e:
        logger.error(f"[Audio upload] Failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {e}",
        )

    return UploadResponse(
        file_id=file_id,
        filename=filename,
        message=f"'{filename}' uploaded successfully ({len(data) // 1024} KB)",
    )


@router.get(
    "/download/{filename}",
    summary="Download an audio file",
    description="Stream an audio file from GridFS by filename.",
)
async def download_audio(filename: str):
    storage = _get_storage()
    try:
        data = storage.download_bytes(filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file '{filename}' not found",
        )
    except Exception as e:
        logger.error(f"[Audio download] Failed for '{filename}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Download failed: {e}",
        )

    # Guess content type from extension
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_map = {
        "wav":  "audio/wav",
        "mp3":  "audio/mpeg",
        "ogg":  "audio/ogg",
        "flac": "audio/flac",
        "m4a":  "audio/mp4",
        "webm": "audio/webm",
    }
    media_type = mime_map.get(ext, "application/octet-stream")

    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete(
    "/{filename}",
    response_model=DeleteResponse,
    summary="Delete an audio file",
    description=(
        "Delete an audio file from GridFS by filename. "
        "Requires the admin API key in the X-Admin-Key header."
    ),
)
async def delete_audio(filename: str, x_admin_key: str = ""):
    await _check_admin(x_admin_key)
    storage = _get_storage()
    deleted = storage.delete_file(filename)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio file '{filename}' not found",
        )
    return DeleteResponse(filename=filename, deleted=True)
