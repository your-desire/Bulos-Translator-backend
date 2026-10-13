"""
Random Trilingual Sample from dataset.xlsx
==========================================
Draws 100 random entries from all usable sheets (COMMON WORDS, WORDS, SENTENCES),
deduplicates, and writes a spreadsheet with three columns:
  Bulos | Filipino | English

Usage:
    python scripts/sample_trilingual.py

Output: scripts/trilingual_sample_<timestamp>.xlsx
No other files are modified.
"""

import random
import sys
from datetime import datetime
from pathlib import Path

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SCRIPT_DIR   = Path(__file__).parent
DATASET_PATH = SCRIPT_DIR.parent / "data" / "dataset.xlsx"
SAMPLE_SIZE  = 100
RANDOM_SEED  = 42

# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------

HEADER_FILL  = PatternFill("solid", fgColor="2F5496")
HEADER_FONT  = Font(bold=True, color="FFFFFF")
HEADER_ALIGN = Alignment(horizontal="center", vertical="center", wrap_text=True)
DATA_ALIGN   = Alignment(wrap_text=True, vertical="top")

ROW_FILL_A = PatternFill("solid", fgColor="EBF3FB")   # light blue (alternating)
ROW_FILL_B = PatternFill("solid", fgColor="FFFFFF")   # white

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

def load_entries(path: Path) -> list[tuple[str, str, str]]:
    """
    Return all (bulos, filipino, english) triples from the dataset,
    skipping blanks and deduplicating on the Bulos column.
    """
    wb      = openpyxl.load_workbook(str(path), data_only=True)
    entries = []
    seen    = set()

    # Sheet name → (bulos_col, filipino_col, english_col) — 0-indexed
    sheet_cols = {
        "COMMON WORDS": (0, 1, 2),
        "WORDS ":       (0, 1, 2),
        "SENTENCES":    (0, 1, 2),   # headers: BULOS, TAGALOG, ENGLISH
    }

    for sheet_name, (bc, fc, ec) in sheet_cols.items():
        if sheet_name not in wb.sheetnames:
            continue
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=2, values_only=True):
            bul = str(row[bc]).strip() if row[bc] else ""
            fil = str(row[fc]).strip() if row[fc] else ""
            eng = str(row[ec]).strip() if row[ec] else ""
            if not bul or not fil or not eng:
                continue
            if bul.lower() in seen:
                continue
            seen.add(bul.lower())
            entries.append((bul, fil, eng))

    return entries

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    if not DATASET_PATH.exists():
        print(f"ERROR: dataset not found at {DATASET_PATH}")
        sys.exit(1)

    print(f"Loading {DATASET_PATH} ...")
    entries = load_entries(DATASET_PATH)
    print(f"Found {len(entries)} unique entries")

    if len(entries) < SAMPLE_SIZE:
        print(f"WARNING: only {len(entries)} entries available — using all of them")
        sample = entries
    else:
        rng    = random.Random(RANDOM_SEED)
        sample = rng.sample(entries, SAMPLE_SIZE)
        # Sort alphabetically by Bulos for readability
        sample.sort(key=lambda t: t[0].lower())

    # ── Build spreadsheet ──────────────────────────────────────────────────
    wb = Workbook()
    ws = wb.active
    ws.title = "Trilingual Sample"

    headers = ["#", "Bulos", "Filipino", "English"]
    widths  = [5, 35, 35, 35]

    for ci, (h, w) in enumerate(zip(headers, widths), 1):
        cell           = ws.cell(row=1, column=ci, value=h)
        cell.font      = HEADER_FONT
        cell.fill      = HEADER_FILL
        cell.alignment = HEADER_ALIGN
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.row_dimensions[1].height = 25
    ws.freeze_panes = "A2"

    for ri, (bul, fil, eng) in enumerate(sample, 2):
        row_fill = ROW_FILL_A if ri % 2 == 0 else ROW_FILL_B
        for ci, value in enumerate([ri - 1, bul, fil, eng], 1):
            cell           = ws.cell(ri, ci, value)
            cell.fill      = row_fill
            cell.alignment = DATA_ALIGN if ci > 1 else Alignment(horizontal="center", vertical="top")

    # Totals row
    last = len(sample) + 2
    ws.cell(last, 1, "Total").font = Font(bold=True)
    ws.cell(last, 2, len(sample)).font = Font(bold=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = SCRIPT_DIR / f"trilingual_sample_{timestamp}.xlsx"
    wb.save(str(out_path))
    print(f"Saved {len(sample)} entries → {out_path}")


if __name__ == "__main__":
    main()
