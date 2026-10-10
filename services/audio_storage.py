"""
GridFS Audio Storage Service for Bulos STT Pipeline.

Connects to the `bulos_audio` database on MongoDB Atlas which already has
403 audio files stored in GridFS (fs.files / fs.chunks).

Existing data format:
  - filename IS the Bulos word/phrase + ".mp3" (e.g. "abi.mp3", "abi-abi.mp3")
  - metadata.contentType = "audio/mpeg"
  - The transcript is derived from the filename: strip extension, replace
    hyphens with spaces → "abi-abi.mp3" becomes "abi abi"

This service provides:
  - Access to existing audio files for STT training
  - Upload of new audio + transcript pairs
  - Training data management (validation, export)
"""

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any, AsyncGenerator

import certifi
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket

logger = logging.getLogger(__name__)


def _transcript_from_filename(filename: str) -> str:
    """
    Derive the Bulos transcript from a GridFS filename.

    Examples:
        "abi.mp3"       → "abi"
        "abi-abi.mp3"   → "abi abi"
        "alayu.mp3"     → "alayu"
        "apoy.mp3"      → "apoy"
    """
    stem = Path(filename).stem          # strip extension
    transcript = stem.replace("-", " ") # hyphens → spaces
    return transcript.strip()


class AudioStorageService:
    """
    Manages audio file storage in MongoDB GridFS for STT training and inference.

    Uses the `bulos_audio` database (separate from `bulos_translator`).

    Collections:
      - fs.files   : GridFS file metadata (403 existing Bulos audio files)
      - fs.chunks  : GridFS binary chunks
      - stt_training_pairs : index linking audio → transcript for training
    """

    def __init__(self, db):
        """
        Args:
            db: AsyncIOMotorDatabase instance for `bulos_audio`
        """
        self.db = db
        self.fs = AsyncIOMotorGridFSBucket(db)
        self.training_collection = db["stt_training_pairs"]
        logger.info("AudioStorageService initialized with GridFS bucket (bulos_audio)")

    async def ensure_indexes(self) -> None:
        """Create indexes for efficient querying."""
        await self.training_collection.create_index("language")
        await self.training_collection.create_index("is_validated")
        await self.training_collection.create_index(
            [("language", 1), ("is_validated", 1)]
        )
        await self.training_collection.create_index("gridfs_file_id", unique=True)
        logger.info("AudioStorageService indexes ensured")

    # ------------------------------------------------------------------
    # Sync existing GridFS files into training pairs
    # ------------------------------------------------------------------

    async def sync_existing_audio_to_training_pairs(self) -> Dict[str, int]:
        """
        Scan all existing GridFS audio files and create stt_training_pairs
        documents for any that don't already have one.

        The transcript is derived from the filename (e.g. "abi-abi.mp3" → "abi abi").

        Returns:
            Dict with counts: {"total_files", "already_synced", "newly_created", "skipped"}
        """
        stats = {"total_files": 0, "already_synced": 0, "newly_created": 0, "skipped": 0}

        cursor = self.db["fs.files"].find({})
        async for doc in cursor:
            stats["total_files"] += 1
            file_id = str(doc["_id"])
            filename = doc.get("filename", "")

            if not filename:
                stats["skipped"] += 1
                continue

            # Check if training pair already exists
            existing = await self.training_collection.find_one(
                {"gridfs_file_id": file_id}
            )
            if existing:
                stats["already_synced"] += 1
                continue

            # Derive transcript from filename
            transcript = _transcript_from_filename(filename)
            if not transcript:
                stats["skipped"] += 1
                continue

            pair_doc = {
                "gridfs_file_id": file_id,
                "transcript": transcript,
                "language": "bul",
                "duration_seconds": None,
                "is_validated": True,  # existing data is pre-validated
                "source": "gridfs_sync",
                "original_filename": filename,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                await self.training_collection.insert_one(pair_doc)
                stats["newly_created"] += 1
            except Exception as e:
                logger.warning(f"Failed to create pair for {filename}: {e}")
                stats["skipped"] += 1

        logger.info(
            f"Sync complete: {stats['total_files']} files, "
            f"{stats['newly_created']} new pairs, "
            f"{stats['already_synced']} already synced, "
            f"{stats['skipped']} skipped"
        )
        return stats

    # ------------------------------------------------------------------
    # Upload new audio
    # ------------------------------------------------------------------

    async def upload_audio(
        self,
        filename: str,
        audio_data: bytes,
        content_type: str = "audio/wav",
        transcript: Optional[str] = None,
        language: str = "bul",
        duration_seconds: Optional[float] = None,
        sample_rate: Optional[int] = None,
        is_training_data: bool = True,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store an audio file in GridFS with metadata.

        Returns:
            str: The GridFS file_id as a hex string
        """
        metadata: Dict[str, Any] = {
            "contentType": content_type,
            "language": language,
            "transcript": transcript,
            "duration_seconds": duration_seconds,
            "sample_rate": sample_rate,
            "is_training_data": is_training_data,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        grid_in = self.fs.open_upload_stream(filename, metadata=metadata)
        await grid_in.write(audio_data)
        await grid_in.close()

        file_id = str(grid_in._id)
        logger.info(
            f"Uploaded audio: {filename} ({len(audio_data)} bytes) → GridFS id={file_id}"
        )

        # Auto-derive transcript from filename if not explicitly given
        if transcript is None:
            transcript = _transcript_from_filename(filename)

        if is_training_data and transcript:
            await self._create_training_pair(file_id, transcript, language, duration_seconds)

        return file_id

    async def _create_training_pair(
        self,
        file_id: str,
        transcript: str,
        language: str,
        duration_seconds: Optional[float],
    ) -> None:
        """Insert a training pair document linking audio to its transcript."""
        doc = {
            "gridfs_file_id": file_id,
            "transcript": transcript,
            "language": language,
            "duration_seconds": duration_seconds,
            "is_validated": False,
            "source": "upload",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.training_collection.insert_one(doc)
            logger.debug(f"Training pair created for audio {file_id}")
        except Exception as e:
            logger.warning(f"Training pair insert failed for {file_id}: {e}")

    # ------------------------------------------------------------------
    # Download / Retrieve
    # ------------------------------------------------------------------

    async def download_audio(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Download an audio file from GridFS by its ID."""
        try:
            oid = ObjectId(file_id)
            grid_out = await self.fs.open_download_stream(oid)
            data = await grid_out.read()
            return {
                "data": data,
                "filename": grid_out.filename,
                "metadata": grid_out.metadata or {},
                "length": grid_out.length,
            }
        except Exception as e:
            logger.error(f"Failed to download audio {file_id}: {e}")
            return None

    async def get_audio_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an audio file without downloading the binary."""
        try:
            oid = ObjectId(file_id)
            doc = await self.db["fs.files"].find_one({"_id": oid})
            if doc is None:
                return None
            return {
                "file_id": str(doc["_id"]),
                "filename": doc.get("filename"),
                "length": doc.get("length"),
                "upload_date": doc.get("uploadDate"),
                "metadata": doc.get("metadata", {}),
                "transcript": _transcript_from_filename(doc.get("filename", "")),
            }
        except Exception as e:
            logger.error(f"Failed to get metadata for {file_id}: {e}")
            return None

    # ------------------------------------------------------------------
    # List / Query
    # ------------------------------------------------------------------

    async def list_audio_files(
        self,
        skip: int = 0,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List audio files stored in GridFS.

        Args:
            skip: Pagination offset
            limit: Max results to return
            search: Optional filename substring filter
        """
        query: Dict[str, Any] = {}
        if search:
            query["filename"] = {"$regex": search, "$options": "i"}

        cursor = (
            self.db["fs.files"]
            .find(query)
            .sort("uploadDate", -1)
            .skip(skip)
            .limit(limit)
        )
        results = []
        async for doc in cursor:
            filename = doc.get("filename", "")
            results.append({
                "file_id": str(doc["_id"]),
                "filename": filename,
                "transcript": _transcript_from_filename(filename),
                "length": doc.get("length"),
                "upload_date": doc.get("uploadDate"),
                "metadata": doc.get("metadata", {}),
            })
        return results

    async def count_audio_files(self) -> int:
        """Count total audio files in GridFS."""
        return await self.db["fs.files"].count_documents({})

    # ------------------------------------------------------------------
    # Training pairs
    # ------------------------------------------------------------------

    async def get_training_pairs(
        self,
        language: str = "bul",
        validated_only: bool = False,
        skip: int = 0,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Get audio + transcript training pairs."""
        query: Dict[str, Any] = {"language": language}
        if validated_only:
            query["is_validated"] = True

        cursor = self.training_collection.find(query).skip(skip).limit(limit)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        return results

    async def count_training_pairs(
        self,
        language: str = "bul",
        validated_only: bool = False,
    ) -> int:
        """Count training pairs for a language."""
        query: Dict[str, Any] = {"language": language}
        if validated_only:
            query["is_validated"] = True
        return await self.training_collection.count_documents(query)

    async def validate_training_pair(self, pair_id: str, is_valid: bool = True) -> bool:
        """Mark a training pair as validated (quality-checked)."""
        try:
            oid = ObjectId(pair_id)
            result = await self.training_collection.update_one(
                {"_id": oid}, {"$set": {"is_validated": is_valid}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to validate training pair {pair_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_audio(self, file_id: str) -> bool:
        """Delete an audio file from GridFS and its training pair record."""
        try:
            oid = ObjectId(file_id)
            await self.fs.delete(oid)
            await self.training_collection.delete_many({"gridfs_file_id": file_id})
            logger.info(f"Deleted audio {file_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete audio {file_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Bulk export for training
    # ------------------------------------------------------------------

    async def export_training_data(
        self,
        language: str = "bul",
        validated_only: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream training pairs with their audio data for model training.

        Yields dicts with:
          - audio_data: raw bytes
          - transcript: the Bulos text
          - language: language code
          - file_id: GridFS file ID
          - filename: original filename
        """
        query: Dict[str, Any] = {"language": language}
        if validated_only:
            query["is_validated"] = True

        cursor = self.training_collection.find(query)
        async for pair in cursor:
            audio = await self.download_audio(pair["gridfs_file_id"])
            if audio is None:
                logger.warning(
                    f"Training pair {pair['_id']} references missing audio "
                    f"{pair['gridfs_file_id']} — skipping"
                )
                continue
            yield {
                "audio_data": audio["data"],
                "transcript": pair["transcript"],
                "language": pair["language"],
                "duration_seconds": pair.get("duration_seconds"),
                "file_id": pair["gridfs_file_id"],
                "filename": audio.get("filename", ""),
            }


# ---------------------------------------------------------------------------
# Singleton — connects to `bulos_audio` database
# ---------------------------------------------------------------------------

_audio_service: Optional[AudioStorageService] = None


def get_audio_storage() -> AudioStorageService:
    """Get the singleton AudioStorageService instance."""
    if _audio_service is None:
        raise RuntimeError(
            "AudioStorageService not initialized. "
            "Call initialize_audio_storage() during app startup."
        )
    return _audio_service


def initialize_audio_storage(mongodb_url: str, database_name: str = "bulos_audio") -> AudioStorageService:
    """
    Initialize the AudioStorageService with its own MongoDB connection
    to the `bulos_audio` database.

    Args:
        mongodb_url: MongoDB Atlas connection string
        database_name: Database name (default: "bulos_audio")
    """
    global _audio_service

    client = AsyncIOMotorClient(
        mongodb_url,
        maxPoolSize=20,
        minPoolSize=5,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        tlsCAFile=certifi.where(),
    )
    db = client[database_name]
    _audio_service = AudioStorageService(db)
    logger.info(f"AudioStorageService initialized → database: {database_name}")
    return _audio_service
