"""
Bulk-upload audio files to MongoDB Atlas GridFS.

Run this locally whenever you want to push audio files to Atlas.
The Render server will then download them at runtime for STT processing.

Usage:
    # Upload all .wav files in a folder
    python scripts/upload_audio.py --dir path/to/audio --language bul

    # Upload a single file
    python scripts/upload_audio.py --file path/to/clip001.wav --language bul --desc "test clip"

    # List files already stored
    python scripts/upload_audio.py --list

    # Delete a file
    python scripts/upload_audio.py --delete clip001.wav

Requirements:
    pip install pymongo dnspython python-dotenv

Environment:
    Set MONGODB_URI in your .env file (or export it before running).
"""

import argparse
import os
import sys
from pathlib import Path

# Load .env so MONGODB_URI is available when running locally
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass  # python-dotenv optional — user can export MONGODB_URI manually

# Make project root importable
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"}


def get_storage():
    from services.audio_storage import get_audio_storage
    storage = get_audio_storage()
    if not storage.is_available:
        print("ERROR: Could not connect to MongoDB Atlas.")
        print("  Make sure MONGODB_URI is set in your .env file.")
        sys.exit(1)
    return storage


def cmd_list(language: str = ""):
    storage = get_storage()
    files = storage.list_files(language=language)
    if not files:
        print("No audio files found." + (f" (language={language})" if language else ""))
        return
    print(f"\n{'Filename':<30} {'Language':<8} {'Size':>10}  {'Uploaded':<25}  Description")
    print("-" * 90)
    for f in files:
        size_kb = f["size_bytes"] // 1024
        print(
            f"{f['filename']:<30} {f['language']:<8} {size_kb:>8} KB  "
            f"{f['upload_date'][:19]:<25}  {f['description']}"
        )
    print(f"\nTotal: {len(files)} file(s)")


def cmd_upload_dir(directory: str, language: str, description: str, overwrite: bool):
    storage = get_storage()
    path = Path(directory)
    if not path.is_dir():
        print(f"ERROR: '{directory}' is not a directory")
        sys.exit(1)

    files = [f for f in path.iterdir() if f.suffix.lower() in AUDIO_EXTENSIONS]
    if not files:
        print(f"No audio files found in '{directory}'")
        return

    print(f"Found {len(files)} audio file(s) in '{directory}'")
    uploaded, skipped, failed = 0, 0, 0

    for f in sorted(files):
        try:
            size_kb = f.stat().st_size // 1024
            print(f"  Uploading '{f.name}' ({size_kb} KB) ...", end=" ", flush=True)
            storage.upload_file(str(f), language=language, description=description)
            print("OK")
            uploaded += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed += 1

    print(f"\nDone — {uploaded} uploaded, {skipped} skipped, {failed} failed")


def cmd_upload_file(filepath: str, language: str, description: str):
    storage = get_storage()
    path = Path(filepath)
    if not path.exists():
        print(f"ERROR: File not found: '{filepath}'")
        sys.exit(1)
    if path.suffix.lower() not in AUDIO_EXTENSIONS:
        print(f"WARNING: '{path.suffix}' is not a recognised audio extension — uploading anyway")

    size_kb = path.stat().st_size // 1024
    print(f"Uploading '{path.name}' ({size_kb} KB) ...", end=" ", flush=True)
    try:
        file_id = storage.upload_file(str(path), language=language, description=description)
        print(f"OK  (id={file_id})")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)


def cmd_delete(filename: str):
    storage = get_storage()
    print(f"Deleting '{filename}' ...", end=" ", flush=True)
    deleted = storage.delete_file(filename)
    print("OK" if deleted else "NOT FOUND")


def main():
    parser = argparse.ArgumentParser(
        description="Manage audio files in MongoDB Atlas GridFS"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list",   action="store_true", help="List stored files")
    group.add_argument("--dir",    metavar="PATH",      help="Upload all audio files in a directory")
    group.add_argument("--file",   metavar="PATH",      help="Upload a single audio file")
    group.add_argument("--delete", metavar="FILENAME",  help="Delete a file by name")

    parser.add_argument("--language", default="",  help="Language tag (bul, en, tl)")
    parser.add_argument("--desc",     default="",  help="Optional description")
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite if a file with the same name already exists (default: replaces)"
    )

    args = parser.parse_args()

    if args.list:
        cmd_list(language=args.language)
    elif args.dir:
        cmd_upload_dir(args.dir, args.language, args.desc, args.overwrite)
    elif args.file:
        cmd_upload_file(args.file, args.language, args.desc)
    elif args.delete:
        cmd_delete(args.delete)


if __name__ == "__main__":
    main()
