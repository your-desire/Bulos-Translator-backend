"""
Prepare LSTM Training Data from dataset.xlsx
=============================================
Reads dataset.xlsx (COMMON WORDS, WORDS, SENTENCES sheets) and produces
the JSON split files expected by Bulos_LSTM_Training_Ready.ipynb:

  data/lstm_training/
    bul_en/  train.json  val.json  test.json  metadata.json
    en_bul/  ...
    bul_tl/  ...
    tl_bul/  ...

Each JSON file is a list of {"source": "...", "target": "..."} dicts.
Split ratio: 70% train / 15% val / 15% test  (reproducible, seed=42)

Usage:
    python scripts/prepare_lstm_training_data.py
"""

import json
import random
import unicodedata
from pathlib import Path

import openpyxl

PROJECT_ROOT = Path(__file__).parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "dataset.xlsx"
OUTPUT_ROOT  = PROJECT_ROOT / "data" / "lstm_training"
RANDOM_SEED  = 42
TRAIN_RATIO  = 0.70
VAL_RATIO    = 0.15   # remaining 15% → test

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clean(val) -> str:
    """Strip whitespace; return empty string for None/blank."""
    return str(val).strip() if val is not None else ""


def strip_diacritics(text: str) -> str:
    """NFD-decompose and remove combining marks (for dedup key only)."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def split_data(pairs: list, seed: int, train_r: float, val_r: float):
    rng = random.Random(seed)
    data = list(pairs)
    rng.shuffle(data)
    n      = len(data)
    n_tr   = int(n * train_r)
    n_val  = int(n * val_r)
    return data[:n_tr], data[n_tr:n_tr + n_val], data[n_tr + n_val:]


def save_split(split: list, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(split, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Load raw triplets
# ---------------------------------------------------------------------------

def load_triplets(xlsx_path: Path) -> list[tuple[str, str, str]]:
    """
    Return all (bulos, tagalog, english) triples from the dataset,
    deduplicating on the Bulos column.
    """
    wb = openpyxl.load_workbook(str(xlsx_path), data_only=True)

    # Sheet → (bulos_col, tagalog_col, english_col) 0-indexed
    sheet_map = {
        "COMMON WORDS": (0, 1, 2),
        "WORDS ":       (0, 1, 2),
        "SENTENCES":    (0, 1, 2),
    }

    triplets = []
    seen: set[str] = set()

    for sheet_name, (bc, tc, ec) in sheet_map.items():
        if sheet_name not in wb.sheetnames:
            print(f"  WARNING: sheet '{sheet_name}' not found — skipping")
            continue

        ws   = wb[sheet_name]
        rows = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            bul = clean(row[bc])
            tl  = clean(row[tc])
            en  = clean(row[ec])
            if not (bul and tl and en):
                continue
            key = strip_diacritics(bul)
            if key in seen:
                continue
            seen.add(key)
            triplets.append((bul, tl, en))
            rows += 1
        print(f"  {sheet_name}: {rows} unique triplets loaded")

    return triplets


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Loading dataset: {DATASET_PATH}")
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"dataset.xlsx not found at {DATASET_PATH}")

    triplets = load_triplets(DATASET_PATH)
    print(f"\nTotal unique entries: {len(triplets)}")

    # Build per-direction pair lists
    directions = {
        "bul_en":  [(b, e)  for b, t, e in triplets],
        "en_bul":  [(e, b)  for b, t, e in triplets],
        "bul_tl":  [(b, t)  for b, t, e in triplets],
        "tl_bul":  [(t, b)  for b, t, e in triplets],
    }

    print()
    for dir_key, pairs in directions.items():
        out_dir = OUTPUT_ROOT / dir_key

        train_raw, val_raw, test_raw = split_data(
            pairs, RANDOM_SEED, TRAIN_RATIO, VAL_RATIO
        )

        train = [{"source": s, "target": t} for s, t in train_raw]
        val   = [{"source": s, "target": t} for s, t in val_raw]
        test  = [{"source": s, "target": t} for s, t in test_raw]

        save_split(train, out_dir / "train.json")
        save_split(val,   out_dir / "val.json")
        save_split(test,  out_dir / "test.json")

        metadata = {
            "direction":    dir_key,
            "total":        len(pairs),
            "train":        len(train),
            "val":          len(val),
            "test":         len(test),
            "seed":         RANDOM_SEED,
        }
        save_split(metadata, out_dir / "metadata.json")

        print(f"  {dir_key}:  {len(train)} train / {len(val)} val / {len(test)} test  → {out_dir}")

    print(f"\nAll splits saved under: {OUTPUT_ROOT}")


if __name__ == "__main__":
    main()
