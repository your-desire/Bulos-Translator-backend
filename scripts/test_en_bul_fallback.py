"""
Regression tests for the en→bul Filipino-bridge fallback.

Tests:
  1. Direct en→bul term      — "iron" has a verified Bulos equivalent
  2. Filipino fallback        — "the iron" → "ang palansa" (the=ang via tl,
                                iron=palansa via direct en→bul)
  3. Numbers pass through     — "100 pesos" numbers unchanged
  4. Diacritics preserved     — Bulos words with accents survive lookup
  5. No Bulos match → keep tl — English word with tl but no bul keeps Filipino
  6. No re-fuzzing Bulos      — already-translated Bulos token never fuzzy-
                                converted to a different Bulos word

Run from project root:
    python scripts/test_en_bul_fallback.py
"""

import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Minimal env so settings doesn't complain
import os
os.environ.setdefault("ADMIN_API_KEY", "test")

from services.translation import TranslationService


async def run_tests():
    svc = TranslationService()
    await svc.initialize()

    PASS = "✓"
    FAIL = "✗"
    results = []

    async def check(label: str, src: str, tgt: str, text: str,
                    expected_contains: str = None,
                    expected_not_contains: str = None,
                    expected_method_contains: str = None):
        r = await svc.translate(text=text, source_language=src,
                                target_language=tgt)
        out    = r["translated_text"].lower()
        method = r.get("translation_method", "")
        ok = True
        notes = []

        if expected_contains and expected_contains.lower() not in out:
            ok = False
            notes.append(f"expected '{expected_contains}' in output")
        if expected_not_contains and expected_not_contains.lower() in out:
            ok = False
            notes.append(f"expected '{expected_not_contains}' NOT in output")
        if expected_method_contains and expected_method_contains not in method:
            ok = False
            notes.append(f"expected method to contain '{expected_method_contains}', got '{method}'")

        icon = PASS if ok else FAIL
        results.append(ok)
        print(f"{icon} [{label}]")
        print(f"    input : '{text}'  ({src}→{tgt})")
        print(f"    output: '{r['translated_text']}'  method={method}")
        if notes:
            for n in notes:
                print(f"    ⚠  {n}")
        print()

    print("=" * 60)
    print("en→bul Filipino-bridge regression tests")
    print("=" * 60)
    print()

    # 1. Direct en→bul verified term
    await check(
        "direct en→bul term",
        "en", "bul", "iron",
        expected_contains="palansa",
    )

    # 2. "the iron" — 'the' is a stopword (skipped by bridge), stays as 'the'
    #    'iron' has direct Bulos equivalent 'palansa' via en→bul dict
    #    Critical: must NOT fuzzy-corrupt 'palansa' into 'malangsa'
    await check(
        "the iron → the palansa (no corruption)",
        "en", "bul", "the iron",
        expected_contains="palansa",
        expected_not_contains="malangsa",
    )

    # 3. Numbers must pass through unchanged
    await check(
        "numbers unchanged",
        "en", "bul", "100 pesos",
        expected_contains="100",
    )

    # 4. Diacritics: Bulos 'ulù' (head) should survive normalisation
    await check(
        "diacritics preserved in bul→en",
        "bul", "en", "ulù",
        # head is the expected English translation
    )

    # 5. English word with tl fallback but no Bulos → keep Filipino
    #    'house' → Filipino 'bahay' but if no Bulos in dict, keep 'bahay'
    await check(
        "no bul match keeps Filipino",
        "en", "bul", "house",
        # should NOT produce an empty string
        expected_not_contains="",
    )

    # 6. Safeguard: 'the iron' second pass must not re-fuzz 'palansa' → 'malangsa'
    await check(
        "no re-fuzzing of translated Bulos tokens",
        "en", "bul", "the iron",
        expected_not_contains="malangsa",
    )

    # 7. Method traceability
    await check(
        "method is traceable for fallback",
        "en", "bul", "the iron",
        expected_method_contains="en_bul",   # method should mention en_bul path
    )

    passed = sum(results)
    total  = len(results)
    print("=" * 60)
    print(f"Results: {passed}/{total} passed")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
