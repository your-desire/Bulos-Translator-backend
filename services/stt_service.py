"""
Speech-to-Text Service for Bulos Translator.

Uses OpenAI Whisper (via faster-whisper / CTranslate2) as the base model,
with support for:
  1. Out-of-the-box transcription using Whisper's multilingual model
  2. Fine-tuned Bulos model loaded from a local path or GridFS

Architecture:
  - Base model: whisper-tiny or whisper-small (multilingual, handles Filipino)
  - Fine-tuned model: Whisper fine-tuned on Bulos audio + transcript pairs
  - Inference: faster-whisper (CTranslate2) for fast CPU inference on Render

The fine-tuning itself happens offline (see scripts/train_stt.py).
This service handles inference only.
"""

import io
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_stt_model = None
_model_info: Dict[str, Any] = {
    "status": "not_loaded",
    "model_size": None,
    "model_path": None,
    "device": "cpu",
    "compute_type": "int8",
}


def _get_model():
    """Return the loaded faster-whisper model singleton."""
    global _stt_model
    if _stt_model is None:
        _load_model()
    return _stt_model


def _load_model(
    model_size_or_path: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> None:
    """
    Load the Whisper model for inference.

    Args:
        model_size_or_path: Either a Whisper model size ("tiny", "small", "medium")
                            or an absolute path to a fine-tuned CTranslate2 model dir.
                            Defaults to env STT_MODEL_PATH or "tiny".
        device: "cpu" or "cuda"
        compute_type: "int8", "float16", "float32"
    """
    global _stt_model, _model_info

    if model_size_or_path is None:
        model_size_or_path = os.environ.get("STT_MODEL_PATH", "tiny")

    try:
        from faster_whisper import WhisperModel

        logger.info(
            f"Loading Whisper STT model: {model_size_or_path} "
            f"(device={device}, compute_type={compute_type})"
        )

        _stt_model = WhisperModel(
            model_size_or_path,
            device=device,
            compute_type=compute_type,
        )

        _model_info.update({
            "status": "loaded",
            "model_size": model_size_or_path,
            "model_path": model_size_or_path,
            "device": device,
            "compute_type": compute_type,
        })

        logger.info(f"Whisper STT model loaded successfully: {model_size_or_path}")

    except Exception as e:
        _model_info["status"] = f"failed: {e}"
        logger.error(f"Failed to load Whisper STT model: {e}", exc_info=True)
        raise


def get_model_info() -> Dict[str, Any]:
    """Return current model status and info."""
    return dict(_model_info)


# ---------------------------------------------------------------------------
# Transcription
# ---------------------------------------------------------------------------


class STTService:
    """
    Speech-to-Text service using faster-whisper.

    Supports:
      - Transcribe audio bytes → text
      - Language detection
      - Forced language hint for Bulos (treated as Filipino/Tagalog by Whisper,
        then post-processed)
    """

    # Whisper language codes — Bulos isn't in Whisper's vocabulary,
    # so we map it to Filipino (tl) which is the closest supported language.
    # The fine-tuned model will learn Bulos phonetics from the training data.
    LANG_MAP = {
        "bul": "tl",  # Bulos → Filipino (closest Whisper language)
        "tl": "tl",   # Filipino / Tagalog
        "en": "en",   # English
    }

    def __init__(self):
        logger.info("STTService initialized")

    async def transcribe(
        self,
        audio_data: bytes,
        language: Optional[str] = None,
        beam_size: int = 5,
        best_of: int = 5,
        temperature: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio file bytes (WAV, MP3, OGG, FLAC, etc.)
            language: Source language hint ("bul", "en", "tl") or None for auto-detect.
                      For Bulos, this maps to "tl" internally since Whisper
                      doesn't know Bulos — the fine-tuned model handles the rest.
            beam_size: Beam search width (higher = more accurate, slower)
            best_of: Number of candidates to consider
            temperature: Sampling temperature (0 = greedy)

        Returns:
            Dict with:
              - text: full transcribed text
              - segments: list of {start, end, text} segments
              - language: detected or forced language code
              - language_probability: confidence of language detection
              - duration: audio duration in seconds
        """
        import asyncio

        model = _get_model()
        if model is None:
            return {
                "text": "",
                "segments": [],
                "language": language or "unknown",
                "language_probability": 0.0,
                "duration": 0.0,
                "error": "STT model not loaded",
            }

        # Map language hint for Whisper
        whisper_lang = None
        if language:
            whisper_lang = self.LANG_MAP.get(language, language)

        # Write audio to a temp file (faster-whisper needs a file path)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: self._transcribe_sync(
                audio_data, whisper_lang, beam_size, best_of, temperature
            ),
        )
        return result

    def _transcribe_sync(
        self,
        audio_data: bytes,
        whisper_lang: Optional[str],
        beam_size: int,
        best_of: int,
        temperature: float,
    ) -> Dict[str, Any]:
        """Synchronous transcription — runs in executor."""
        model = _get_model()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(audio_data)
            tmp.flush()

            try:
                segments_gen, info = model.transcribe(
                    tmp.name,
                    language=whisper_lang,
                    beam_size=beam_size,
                    best_of=best_of,
                    temperature=temperature,
                    vad_filter=True,          # filter out silence
                    vad_parameters=dict(
                        min_silence_duration_ms=500,
                    ),
                )

                segments = []
                full_text_parts = []
                for seg in segments_gen:
                    segments.append({
                        "start": round(seg.start, 2),
                        "end": round(seg.end, 2),
                        "text": seg.text.strip(),
                    })
                    full_text_parts.append(seg.text.strip())

                full_text = " ".join(full_text_parts)

                logger.info(
                    f"Transcription complete: lang={info.language} "
                    f"prob={info.language_probability:.2f} "
                    f"duration={info.duration:.1f}s "
                    f"text='{full_text[:80]}...'"
                )

                return {
                    "text": full_text,
                    "segments": segments,
                    "language": info.language,
                    "language_probability": round(info.language_probability, 3),
                    "duration": round(info.duration, 2),
                }

            except Exception as e:
                logger.error(f"Transcription failed: {e}", exc_info=True)
                return {
                    "text": "",
                    "segments": [],
                    "language": whisper_lang or "unknown",
                    "language_probability": 0.0,
                    "duration": 0.0,
                    "error": str(e),
                }

    async def detect_language(self, audio_data: bytes) -> Dict[str, Any]:
        """
        Detect the spoken language from audio without full transcription.

        Returns:
            Dict with detected_language and probability
        """
        # Use transcribe with a short segment for detection
        result = await self.transcribe(audio_data, language=None, beam_size=1, best_of=1)
        return {
            "detected_language": result.get("language", "unknown"),
            "probability": result.get("language_probability", 0.0),
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_stt_service: Optional[STTService] = None


def get_stt_service() -> STTService:
    """Get the singleton STTService instance."""
    global _stt_service
    if _stt_service is None:
        _stt_service = STTService()
    return _stt_service


def initialize_stt_service(
    model_size_or_path: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8",
) -> STTService:
    """
    Initialize the STT model and service.

    Call during app startup (in lifespan) to pre-load the model.
    """
    global _stt_service
    _load_model(model_size_or_path, device, compute_type)
    _stt_service = STTService()
    logger.info("STTService initialized and model loaded")
    return _stt_service
