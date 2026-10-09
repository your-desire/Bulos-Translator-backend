"""
STT (Speech-to-Text) API Router for Bulos Translator.

Endpoints:
  POST /api/v1/stt/transcribe        — Transcribe audio to text
  POST /api/v1/stt/upload-training   — Upload audio + transcript training pair
  GET  /api/v1/stt/training-data     — List training pairs
  GET  /api/v1/stt/training-data/stats — Training data statistics
  PUT  /api/v1/stt/training-data/{id}/validate — Validate a training pair
  GET  /api/v1/stt/model-status      — Check STT model status
  GET  /api/v1/stt/audio/{file_id}   — Download an audio file
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, Query, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stt", tags=["Speech-to-Text"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TranscriptionSegment(BaseModel):
    start: float
    end: float
    text: str


class TranscriptionResponse(BaseModel):
    text: str
    segments: list
    language: str
    language_probability: float
    duration: float
    error: Optional[str] = None


class UploadTrainingResponse(BaseModel):
    file_id: str
    filename: str
    transcript: str
    language: str
    size_bytes: int
    message: str


class ModelStatusResponse(BaseModel):
    status: str
    model_size: Optional[str] = None
    model_path: Optional[str] = None
    device: str = "cpu"
    compute_type: str = "int8"
    training_pairs_total: int = 0
    training_pairs_validated: int = 0


class TrainingStatsResponse(BaseModel):
    total_pairs: int
    validated_pairs: int
    total_audio_files: int
    languages: dict


# ---------------------------------------------------------------------------
# POST /transcribe — Transcribe audio file to text
# ---------------------------------------------------------------------------


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    audio: UploadFile = File(..., description="Audio file (WAV, MP3, OGG, FLAC, WebM)"),
    language: Optional[str] = Form(
        None,
        description="Source language hint: 'bul', 'en', 'tl'. "
                    "Leave empty for auto-detection.",
    ),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
):
    """
    Transcribe an audio file to text using the Whisper STT model.

    For Bulos audio, set language='bul' — the model uses Filipino (tl) as
    the closest base language and applies Bulos-specific recognition from
    fine-tuning.

    Accepts: WAV, MP3, OGG, FLAC, WebM, M4A
    Max recommended size: 25 MB
    """
    # Validate language
    if language and language not in ("bul", "en", "tl"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {language}. Use 'bul', 'en', or 'tl'.",
        )

    # Validate file type
    allowed_types = {
        "audio/wav", "audio/x-wav", "audio/wave",
        "audio/mp3", "audio/mpeg",
        "audio/ogg", "audio/opus",
        "audio/flac", "audio/x-flac",
        "audio/webm",
        "audio/mp4", "audio/m4a", "audio/x-m4a",
        "application/octet-stream",  # fallback for unknown types
    }
    content_type = audio.content_type or "application/octet-stream"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format: {content_type}. "
                   f"Use WAV, MP3, OGG, FLAC, or WebM.",
        )

    # Read audio data
    audio_data = await audio.read()
    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_data) > 25 * 1024 * 1024:  # 25 MB limit
        raise HTTPException(status_code=413, detail="Audio file too large (max 25 MB)")

    logger.info(
        f"Transcription request: file={audio.filename} "
        f"size={len(audio_data)} bytes, lang={language}, "
        f"device={x_device_id}"
    )

    # Transcribe
    try:
        from services.stt_service import get_stt_service
        stt = get_stt_service()
        result = await stt.transcribe(audio_data, language=language)
        return TranscriptionResponse(**result)
    except RuntimeError as e:
        if "not loaded" in str(e).lower() or "not initialized" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="STT model is not loaded. The server may still be starting up.",
            )
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Transcription failed")


# ---------------------------------------------------------------------------
# POST /upload-training — Upload audio + transcript pair for training
# ---------------------------------------------------------------------------


@router.post("/upload-training", response_model=UploadTrainingResponse)
async def upload_training_data(
    audio: UploadFile = File(..., description="Audio file of Bulos speech"),
    transcript: str = Form(..., description="The Bulos text spoken in the audio"),
    language: str = Form("bul", description="Language code: 'bul', 'en', 'tl'"),
    duration_seconds: Optional[float] = Form(
        None, description="Audio duration in seconds (auto-detected if omitted)"
    ),
    x_device_id: Optional[str] = Header(None, alias="X-Device-ID"),
):
    """
    Upload an audio recording paired with its transcript for STT training.

    This builds the training dataset. Each pair consists of:
    - An audio file (WAV recommended, any format accepted)
    - The exact text that was spoken (transcript)

    The pair is stored in GridFS and indexed for later model training.
    """
    if language not in ("bul", "en", "tl"):
        raise HTTPException(status_code=400, detail=f"Invalid language: {language}")

    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty")

    audio_data = await audio.read()
    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="Empty audio file")

    content_type = audio.content_type or "audio/wav"

    logger.info(
        f"Training upload: file={audio.filename} size={len(audio_data)} "
        f"transcript='{transcript[:50]}...' lang={language}"
    )

    try:
        from services.audio_storage import get_audio_storage
        storage = get_audio_storage()

        file_id = await storage.upload_audio(
            filename=audio.filename or "training_audio.wav",
            audio_data=audio_data,
            content_type=content_type,
            transcript=transcript.strip(),
            language=language,
            duration_seconds=duration_seconds,
            is_training_data=True,
            extra_metadata={"device_id": x_device_id},
        )

        return UploadTrainingResponse(
            file_id=file_id,
            filename=audio.filename or "training_audio.wav",
            transcript=transcript.strip(),
            language=language,
            size_bytes=len(audio_data),
            message="Training pair uploaded successfully",
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Training upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to upload training data")


# ---------------------------------------------------------------------------
# GET /training-data — List training pairs
# ---------------------------------------------------------------------------


@router.get("/training-data")
async def list_training_data(
    language: str = Query("bul", description="Language filter"),
    validated_only: bool = Query(False, description="Show only validated pairs"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    """List audio + transcript training pairs."""
    try:
        from services.audio_storage import get_audio_storage
        storage = get_audio_storage()
        pairs = await storage.get_training_pairs(
            language=language,
            validated_only=validated_only,
            skip=skip,
            limit=limit,
        )
        total = await storage.count_training_pairs(language=language, validated_only=validated_only)
        return {
            "pairs": pairs,
            "total": total,
            "skip": skip,
            "limit": limit,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# GET /training-data/stats — Training data statistics
# ---------------------------------------------------------------------------


@router.get("/training-data/stats", response_model=TrainingStatsResponse)
async def training_data_stats():
    """Get statistics about the training data in GridFS."""
    try:
        from services.audio_storage import get_audio_storage
        storage = get_audio_storage()

        total_bul = await storage.count_training_pairs("bul")
        validated_bul = await storage.count_training_pairs("bul", validated_only=True)
        total_en = await storage.count_training_pairs("en")
        total_tl = await storage.count_training_pairs("tl")
        total_audio = await storage.count_audio_files()

        return TrainingStatsResponse(
            total_pairs=total_bul + total_en + total_tl,
            validated_pairs=validated_bul,
            total_audio_files=total_audio,
            languages={
                "bul": total_bul,
                "en": total_en,
                "tl": total_tl,
            },
        )
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# PUT /training-data/{pair_id}/validate — Validate a training pair
# ---------------------------------------------------------------------------


@router.put("/training-data/{pair_id}/validate")
async def validate_training_pair(
    pair_id: str,
    is_valid: bool = Query(True, description="Mark as valid or invalid"),
):
    """Mark a training pair as validated (quality-checked) for model training."""
    try:
        from services.audio_storage import get_audio_storage
        storage = get_audio_storage()
        updated = await storage.validate_training_pair(pair_id, is_valid)
        if not updated:
            raise HTTPException(status_code=404, detail="Training pair not found")
        return {"message": f"Training pair {pair_id} validation set to {is_valid}"}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))


# ---------------------------------------------------------------------------
# GET /model-status — Check STT model status
# ---------------------------------------------------------------------------


@router.get("/model-status", response_model=ModelStatusResponse)
async def model_status():
    """Check the current status of the STT model."""
    from services.stt_service import get_model_info

    info = get_model_info()

    # Add training data stats
    try:
        from services.audio_storage import get_audio_storage
        storage = get_audio_storage()
        info["training_pairs_total"] = await storage.count_training_pairs("bul")
        info["training_pairs_validated"] = await storage.count_training_pairs(
            "bul", validated_only=True
        )
    except Exception:
        info["training_pairs_total"] = 0
        info["training_pairs_validated"] = 0

    return ModelStatusResponse(**info)


# ---------------------------------------------------------------------------
# GET /audio/{file_id} — Download audio from GridFS
# ---------------------------------------------------------------------------


@router.get("/audio/{file_id}")
async def download_audio(file_id: str):
    """Download an audio file from GridFS by its ID."""
    try:
        from services.audio_storage import get_audio_storage
        storage = get_audio_storage()
        result = await storage.download_audio(file_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Audio file not found")

        content_type = result["metadata"].get("content_type", "audio/wav")
        return StreamingResponse(
            iter([result["data"]]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{result["filename"]}"',
                "Content-Length": str(result["length"]),
            },
        )
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))