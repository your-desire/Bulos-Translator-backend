"""
Audio Storage Service — MongoDB Atlas GridFS
=============================================
Stores and retrieves audio files using GridFS so the Render server can
download them at runtime for Speech-to-Text processing.

Each file is stored with metadata:
  filename     — original file name (e.g. "clip001.wav")
  content_type — MIME type (e.g. "audio/wav", "audio/mpeg")
  language     — language tag (e.g. "bul", "en", "tl")
  description  — optional free-text note

Usage on Render (download before STT):
    from services.audio_storage import get_audio_storage
    storage = get_audio_storage()
    path = storage.download_to_temp("clip001.wav")   # returns "/tmp/clip001.wav"
    # ... run STT on path ...
    storage.delete_temp(path)                        # clean up /tmp
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

from utils.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional["AudioStorageService"] = None


def get_audio_storage() -> "AudioStorageService":
    """Return the module-level AudioStorageService singleton."""
    global _instance
    if _instance is None:
        _instance = AudioStorageService()
        _instance.connect()
    return _instance


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class AudioStorageService:
    """
    Wraps MongoDB GridFS for audio file storage.
    All heavy imports are deferred so the module loads even without pymongo.
    """

    def __init__(self):
        self._client = None
        self._db     = None
        self._fs     = None

    # ── Connection ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Open connection to MongoDB Atlas. Called once at startup."""
        try:
            from pymongo import MongoClient
            import gridfs

            uri = os.environ.get("MONGODB_URI", "")
            if not uri:
                logger.warning(
                    "[AudioStorage] MONGODB_URI not set — audio storage unavailable"
                )
                return

            db_name = os.environ.get("MONGODB_AUDIO_DB", "bulos_audio")

            logger.info(f"[AudioStorage] Connecting to MongoDB (db={db_name}) ...")
            self._client = MongoClient(uri, serverSelectionTimeoutMS=10_000)
            # Verify the connection is alive
            self._client.admin.command("ping")
            self._db = self._client[db_name]
            self._fs = gridfs.GridFS(self._db)
            logger.info("[AudioStorage] Connected — GridFS ready")

        except Exception as e:
            logger.error(f"[AudioStorage] Connection failed: {e}", exc_info=True)
            self._client = self._db = self._fs = None

    @property
    def is_available(self) -> bool:
        return self._fs is not None

    def _require_fs(self):
        if not self.is_available:
            raise RuntimeError(
                "Audio storage is unavailable. "
                "Check MONGODB_URI and Atlas network settings."
            )

    # ── Upload ───────────────────────────────────────────────────────────────

    def upload(
        self,
        file_bytes: bytes,
        filename:   str,
        content_type: str = "audio/wav",
        language:   str   = "",
        description: str  = "",
    ) -> str:
        """
        Upload audio bytes to GridFS.
        Returns the string representation of the new GridFS file ID.
        Raises if a file with the same name already exists (use overwrite=True to replace).
        """
        self._require_fs()

        # Remove any existing file with the same name first
        existing = self._fs.find_one({"filename": filename})
        if existing:
            self._fs.delete(existing._id)
            logger.debug(f"[AudioStorage] Replaced existing file: {filename}")

        file_id = self._fs.put(
            file_bytes,
            filename=filename,
            content_type=content_type,
            metadata={
                "language":    language,
                "description": description,
                "size_bytes":  len(file_bytes),
            },
        )
        logger.info(
            f"[AudioStorage] Uploaded '{filename}' "
            f"({len(file_bytes) // 1024} KB, id={file_id})"
        )
        return str(file_id)

    def upload_file(
        self,
        file_path:   str,
        language:    str = "",
        description: str = "",
    ) -> str:
        """Convenience wrapper: upload from a local file path."""
        path = Path(file_path)
        suffix = path.suffix.lower()
        mime_map = {
            ".wav":  "audio/wav",
            ".mp3":  "audio/mpeg",
            ".ogg":  "audio/ogg",
            ".flac": "audio/flac",
            ".m4a":  "audio/mp4",
            ".webm": "audio/webm",
        }
        content_type = mime_map.get(suffix, "application/octet-stream")

        with open(file_path, "rb") as f:
            data = f.read()

        return self.upload(
            data,
            filename=path.name,
            content_type=content_type,
            language=language,
            description=description,
        )

    # ── Download ─────────────────────────────────────────────────────────────

    def download_bytes(self, filename: str) -> bytes:
        """Download a file from GridFS and return its raw bytes."""
        self._require_fs()
        grid_out = self._fs.find_one({"filename": filename})
        if grid_out is None:
            raise FileNotFoundError(
                f"Audio file '{filename}' not found in GridFS"
            )
        return grid_out.read()

    def download_to_temp(self, filename: str) -> str:
        """
        Download a file from GridFS into /tmp and return the local path.
        The caller is responsible for deleting the file after use.
        """
        data = self.download_bytes(filename)
        suffix = Path(filename).suffix
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=suffix, dir="/tmp")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                f.write(data)
        except Exception:
            os.close(tmp_fd)
            raise
        logger.debug(
            f"[AudioStorage] Downloaded '{filename}' → {tmp_path} "
            f"({len(data) // 1024} KB)"
        )
        return tmp_path

    @staticmethod
    def delete_temp(path: str) -> None:
        """Delete a temp file created by download_to_temp()."""
        try:
            os.remove(path)
            logger.debug(f"[AudioStorage] Deleted temp file: {path}")
        except OSError:
            pass

    # ── List / Delete ────────────────────────────────────────────────────────

    def list_files(self, language: str = "") -> list[dict]:
        """
        Return metadata for all stored audio files.
        Pass language="bul" to filter by language tag.
        """
        self._require_fs()
        query = {}
        if language:
            query["metadata.language"] = language

        results = []
        for grid_out in self._fs.find(query):
            meta = grid_out.metadata or {}
            results.append({
                "id":           str(grid_out._id),
                "filename":     grid_out.filename,
                "content_type": getattr(grid_out, "content_type", ""),
                "size_bytes":   meta.get("size_bytes", grid_out.length),
                "language":     meta.get("language", ""),
                "description":  meta.get("description", ""),
                "upload_date":  grid_out.upload_date.isoformat()
                                if grid_out.upload_date else "",
            })
        return results

    def delete_file(self, filename: str) -> bool:
        """Delete a file from GridFS by filename. Returns True if deleted."""
        self._require_fs()
        grid_out = self._fs.find_one({"filename": filename})
        if grid_out is None:
            return False
        self._fs.delete(grid_out._id)
        logger.info(f"[AudioStorage] Deleted '{filename}' from GridFS")
        return True
