#!/usr/bin/env python3
"""
Bulos STT Model Training Script

Fine-tunes OpenAI Whisper on Bulos audio recordings stored in MongoDB Atlas
GridFS (bulos_audio database, 403+ audio files).

Architecture:
  - Base model: openai/whisper-tiny (or whisper-small for better accuracy)
  - Training data: GridFS audio files where filename = transcript
    e.g. "abi.mp3" → transcript "abi", "abi-abi.mp3" → "abi abi"
  - Output: CTranslate2 model directory for faster-whisper inference

Requirements:
  pip install torch torchaudio transformers datasets evaluate jiwer
  pip install pymongo certifi motor pydub soundfile
  pip install ctranslate2  # for model conversion

Usage:
  # 1. Export training data from GridFS to local directory
  python scripts/train_stt.py export --mongodb-url "mongodb+srv://..." --output-dir ./training_data

  # 2. Fine-tune Whisper on exported data
  python scripts/train_stt.py train --data-dir ./training_data --output-dir ./models/bulos-whisper

  # 3. Convert to CTranslate2 format for faster-whisper
  python scripts/train_stt.py convert --model-dir ./models/bulos-whisper --output-dir ./models/bulos-whisper-ct2

Environment:
  - Run locally or on a GPU machine (Google Colab, etc.)
  - NOT on Render — training requires GPU and more memory
  - After training, upload the CTranslate2 model to the server
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1: Export audio from GridFS to local files
# ---------------------------------------------------------------------------

async def export_from_gridfs(mongodb_url: str, output_dir: str, database_name: str = "bulos_audio"):
    """
    Download all audio files from GridFS and create a training manifest.

    Creates:
      output_dir/
        audio/
          abi.mp3
          abi-abi.mp3
          ...
        manifest.jsonl   ← {audio_path, transcript, language}
    """
    import certifi
    from motor.motor_asyncio import AsyncIOMotorClient

    logger.info(f"Connecting to MongoDB Atlas (database: {database_name})...")
    client = AsyncIOMotorClient(
        mongodb_url,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=15000,
    )
    db = client[database_name]

    # Verify connection
    await db.command("ping")
    logger.info("Connected to MongoDB Atlas")

    # Count files
    total = await db["fs.files"].count_documents({})
    logger.info(f"Found {total} audio files in GridFS")

    # Create output directories
    out = Path(output_dir)
    audio_dir = out / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = out / "manifest.jsonl"
    exported = 0
    skipped = 0

    from motor.motor_asyncio import AsyncIOMotorGridFSBucket
    fs = AsyncIOMotorGridFSBucket(db)

    with open(manifest_path, "w", encoding="utf-8") as manifest:
        cursor = db["fs.files"].find({}).sort("filename", 1)
        async for doc in cursor:
            filename = doc.get("filename", "")
            if not filename:
                skipped += 1
                continue

            file_id = doc["_id"]
            audio_path = audio_dir / filename

            # Download audio
            try:
                grid_out = await fs.open_download_stream(file_id)
                data = await grid_out.read()
                audio_path.write_bytes(data)
            except Exception as e:
                logger.warning(f"Failed to download {filename}: {e}")
                skipped += 1
                continue

            # Derive transcript from filename
            stem = Path(filename).stem
            transcript = stem.replace("-", " ").strip()

            # Write manifest entry
            entry = {
                "audio_path": str(audio_path),
                "transcript": transcript,
                "language": "bul",
                "file_id": str(file_id),
                "filename": filename,
                "size_bytes": len(data),
            }
            manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")
            exported += 1

            if exported % 50 == 0:
                logger.info(f"Exported {exported}/{total} files...")

    client.close()
    logger.info(f"Export complete: {exported} files exported, {skipped} skipped")
    logger.info(f"Manifest: {manifest_path}")
    logger.info(f"Audio dir: {audio_dir}")
    return exported


# ---------------------------------------------------------------------------
# Step 2: Fine-tune Whisper
# ---------------------------------------------------------------------------

def prepare_dataset(data_dir: str, test_split: float = 0.1):
    """
    Load the exported manifest and prepare a HuggingFace Dataset
    for Whisper fine-tuning.
    """
    import json
    from datasets import Dataset, DatasetDict, Audio

    manifest_path = Path(data_dir) / "manifest.jsonl"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest not found: {manifest_path}\n"
            f"Run `python scripts/train_stt.py export` first."
        )

    entries = []
    with open(manifest_path, "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line.strip())
            if Path(entry["audio_path"]).exists():
                entries.append({
                    "audio": entry["audio_path"],
                    "transcript": entry["transcript"],
                })

    logger.info(f"Loaded {len(entries)} training entries from manifest")

    if len(entries) == 0:
        raise ValueError("No valid training entries found")

    # Create dataset
    ds = Dataset.from_list(entries)
    ds = ds.cast_column("audio", Audio(sampling_rate=16000))

    # Split into train/test
    split = ds.train_test_split(test_size=test_split, seed=42)
    logger.info(f"Train: {len(split['train'])} | Test: {len(split['test'])}")

    return split


def train_whisper(
    data_dir: str,
    output_dir: str,
    base_model: str = "openai/whisper-tiny",
    epochs: int = 30,
    batch_size: int = 8,
    learning_rate: float = 1e-5,
    warmup_steps: int = 50,
    gradient_accumulation: int = 2,
    fp16: bool = True,
):
    """
    Fine-tune Whisper on Bulos audio data.

    Args:
        data_dir: Directory with manifest.jsonl and audio/ folder
        output_dir: Where to save the fine-tuned model
        base_model: Base Whisper model to fine-tune
        epochs: Number of training epochs
        batch_size: Per-device batch size
        learning_rate: Learning rate
        warmup_steps: Warmup steps for scheduler
        gradient_accumulation: Gradient accumulation steps
        fp16: Use mixed precision (requires GPU)
    """
    import torch
    from transformers import (
        WhisperProcessor,
        WhisperForConditionalGeneration,
        Seq2SeqTrainingArguments,
        Seq2SeqTrainer,
    )
    from dataclasses import dataclass
    from typing import Any, Dict, List, Union
    import evaluate

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")
    if device == "cpu":
        logger.warning("Training on CPU will be very slow. Use a GPU for better results.")
        fp16 = False  # fp16 not supported on CPU

    # Load processor and model
    logger.info(f"Loading base model: {base_model}")
    processor = WhisperProcessor.from_pretrained(base_model)
    model = WhisperForConditionalGeneration.from_pretrained(base_model)

    # Force Filipino (Tagalog) as the language and transcription task
    # Bulos is closest to Filipino, so we use tl as the language token
    model.config.forced_decoder_ids = processor.get_decoder_prompt_ids(
        language="tl", task="transcribe"
    )
    model.config.suppress_tokens = []

    # Prepare dataset
    dataset = prepare_dataset(data_dir)

    def prepare_features(batch):
        """Process a batch: extract audio features and tokenize transcripts."""
        audio = batch["audio"]
        input_features = processor(
            audio["array"],
            sampling_rate=audio["sampling_rate"],
            return_tensors="pt",
        ).input_features[0]

        labels = processor.tokenizer(batch["transcript"]).input_ids
        return {"input_features": input_features, "labels": labels}

    logger.info("Processing dataset...")
    train_ds = dataset["train"].map(
        prepare_features,
        remove_columns=dataset["train"].column_names,
        num_proc=1,
    )
    eval_ds = dataset["test"].map(
        prepare_features,
        remove_columns=dataset["test"].column_names,
        num_proc=1,
    )

    # Data collator
    @dataclass
    class DataCollatorSpeechSeq2SeqWithPadding:
        processor: Any

        def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
            # Split inputs and labels
            input_features = [{"input_features": f["input_features"]} for f in features]
            batch = self.processor.feature_extractor.pad(input_features, return_tensors="pt")

            label_features = [{"input_ids": f["labels"]} for f in features]
            labels_batch = self.processor.tokenizer.pad(label_features, return_tensors="pt")
            labels = labels_batch["input_ids"].masked_fill(
                labels_batch.attention_mask.ne(1), -100
            )

            # Remove BOS token if present (Whisper adds it during generation)
            if (labels[:, 0] == model.config.decoder_start_token_id).all().cpu().item():
                labels = labels[:, 1:]

            batch["labels"] = labels
            return batch

    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)

    # WER metric
    wer_metric = evaluate.load("wer")

    def compute_metrics(pred):
        pred_ids = pred.predictions
        label_ids = pred.label_ids
        label_ids[label_ids == -100] = processor.tokenizer.pad_token_id
        pred_str = processor.tokenizer.batch_decode(pred_ids, skip_special_tokens=True)
        label_str = processor.tokenizer.batch_decode(label_ids, skip_special_tokens=True)
        wer = wer_metric.compute(predictions=pred_str, references=label_str)
        return {"wer": wer}

    # Training arguments
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation,
        learning_rate=learning_rate,
        warmup_steps=warmup_steps,
        num_train_epochs=epochs,
        fp16=fp16,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        load_best_model_at_end=True,
        metric_for_best_model="wer",
        greater_is_better=False,
        predict_with_generate=True,
        generation_max_length=128,
        report_to="none",
        save_total_limit=3,
        dataloader_num_workers=0,
        remove_unused_columns=False,
    )

    # Trainer
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
        processing_class=processor.feature_extractor,
    )

    logger.info("Starting training...")
    trainer.train()

    # Save final model
    logger.info(f"Saving model to {output_dir}")
    trainer.save_model(output_dir)
    processor.save_pretrained(output_dir)

    logger.info("Training complete!")
    return output_dir


# ---------------------------------------------------------------------------
# Step 3: Convert to CTranslate2 format for faster-whisper
# ---------------------------------------------------------------------------

def convert_to_ctranslate2(model_dir: str, output_dir: str, quantization: str = "int8"):
    """
    Convert the fine-tuned HuggingFace Whisper model to CTranslate2 format
    for use with faster-whisper.

    Args:
        model_dir: Path to the fine-tuned HuggingFace model
        output_dir: Where to save the CTranslate2 model
        quantization: "int8", "float16", or "float32"
    """
    import subprocess

    logger.info(f"Converting {model_dir} → CTranslate2 ({quantization})")

    cmd = [
        sys.executable, "-m", "ctranslate2.converters.transformers",
        "--model", model_dir,
        "--output_dir", output_dir,
        "--quantization", quantization,
        "--force",
    ]

    # Alternative: use ct2-whisper-converter if available
    try:
        result = subprocess.run(
            ["ct2-whisper-converter",
             "--model", model_dir,
             "--output_dir", output_dir,
             "--quantization", quantization],
            capture_output=True, text=True, check=True,
        )
        logger.info(f"CTranslate2 conversion complete: {output_dir}")
        logger.info(result.stdout)
    except FileNotFoundError:
        # Fallback: manual conversion
        logger.info("ct2-whisper-converter not found, using Python API...")
        import ctranslate2

        converter = ctranslate2.converters.TransformersConverter(model_dir)
        converter.convert(output_dir, quantization=quantization, force=True)
        logger.info(f"CTranslate2 conversion complete: {output_dir}")

    # Copy tokenizer files needed by faster-whisper
    import shutil
    for fname in ["tokenizer.json", "preprocessor_config.json", "vocabulary.json",
                  "special_tokens_map.json", "added_tokens.json"]:
        src = Path(model_dir) / fname
        if src.exists():
            shutil.copy2(src, Path(output_dir) / fname)
            logger.info(f"Copied {fname} to output")

    logger.info(f"Model ready for faster-whisper at: {output_dir}")
    logger.info(f"Set STT_MODEL_PATH={output_dir} in your .env to use this model")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Bulos STT Model Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export 403 audio files from GridFS
  python scripts/train_stt.py export \\
    --mongodb-url "mongodb+srv://user:pass@cluster.mongodb.net/" \\
    --output-dir ./training_data

  # Fine-tune Whisper (run on GPU machine)
  python scripts/train_stt.py train \\
    --data-dir ./training_data \\
    --output-dir ./models/bulos-whisper \\
    --base-model openai/whisper-tiny \\
    --epochs 30

  # Convert to CTranslate2 for faster-whisper
  python scripts/train_stt.py convert \\
    --model-dir ./models/bulos-whisper \\
    --output-dir ./models/bulos-whisper-ct2
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Export
    export_parser = subparsers.add_parser("export", help="Export audio from GridFS")
    export_parser.add_argument("--mongodb-url", required=True, help="MongoDB Atlas connection string")
    export_parser.add_argument("--output-dir", default="./training_data", help="Output directory")
    export_parser.add_argument("--database", default="bulos_audio", help="Database name")

    # Train
    train_parser = subparsers.add_parser("train", help="Fine-tune Whisper on Bulos audio")
    train_parser.add_argument("--data-dir", default="./training_data", help="Directory with manifest.jsonl")
    train_parser.add_argument("--output-dir", default="./models/bulos-whisper", help="Model output directory")
    train_parser.add_argument("--base-model", default="openai/whisper-tiny", help="Base Whisper model")
    train_parser.add_argument("--epochs", type=int, default=30, help="Training epochs")
    train_parser.add_argument("--batch-size", type=int, default=8, help="Batch size")
    train_parser.add_argument("--lr", type=float, default=1e-5, help="Learning rate")
    train_parser.add_argument("--no-fp16", action="store_true", help="Disable mixed precision")

    # Convert
    convert_parser = subparsers.add_parser("convert", help="Convert to CTranslate2 format")
    convert_parser.add_argument("--model-dir", required=True, help="Fine-tuned model directory")
    convert_parser.add_argument("--output-dir", required=True, help="CTranslate2 output directory")
    convert_parser.add_argument("--quantization", default="int8", choices=["int8", "float16", "float32"])

    args = parser.parse_args()

    if args.command == "export":
        asyncio.run(export_from_gridfs(args.mongodb_url, args.output_dir, args.database))

    elif args.command == "train":
        train_whisper(
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            base_model=args.base_model,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.lr,
            fp16=not args.no_fp16,
        )

    elif args.command == "convert":
        convert_to_ctranslate2(args.model_dir, args.output_dir, args.quantization)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
