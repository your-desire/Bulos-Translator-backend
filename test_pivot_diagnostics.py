"""
Test pivot diagnostics field population.

Verify that pivot_intermediate and other diagnostic fields are correctly
populated in the API response when pivot translation succeeds.
"""
import asyncio
import pytest
from services.translation import TranslationService
from config import settings


@pytest.mark.asyncio
async def test_pivot_diagnostics_populated():
    """Test that pivot diagnostic fields are present when pivot succeeds."""
    print("\n" + "="*70)
    print("TEST: Pivot Diagnostics Field Population")
    print("="*70)
    
    # Enable pivot for this test
    original_setting = settings.filipino_pivot_enabled
    settings.filipino_pivot_enabled = True
    
    try:
        service = TranslationService()
        await service.initialize()
        
        # Use a phrase that will trigger pivot but might succeed
        # "anak" exists in BUL-TL, so BUL→TL→EN pivot might work
        test_cases = [
            {
                "text": "anak",
                "src": "bul",
                "tgt": "en",
                "description": "Simple word that exists in BUL-TL"
            },
            {
                "text": "salamat ka",
                "src": "bul",
                "tgt": "en",
                "description": "Word combination not in dataset (may trigger pivot)"
            }
        ]
        
        for case in test_cases:
            print(f"\n{case['description']}")
            print(f"  Input: '{case['text']}' ({case['src']}→{case['tgt']})")
            
            result = await service.translate(case['text'], case['src'], case['tgt'])
            
            print(f"  Output: '{result['translated_text']}'")
            print(f"  Method: {result['translation_method']}")
            print(f"  Confidence: {result.get('confidence')}")
            
            # Check if pivot was used
            if result['translation_method'].startswith('filipino_pivot'):
                print("  ✓ Pivot was used!")
                
                # Verify all diagnostic fields are present
                expected_fields = [
                    'pivot_intermediate',
                    'pivot_intermediate_method',
                    'pivot_final_method',
                    'pivot_stage2_elapsed',
                    'pivot_stage3_elapsed',
                    'pivot_path'
                ]
                
                missing_fields = [f for f in expected_fields if f not in result]
                
                if missing_fields:
                    print(f"  ✗ MISSING FIELDS: {missing_fields}")
                    print(f"  Available fields: {list(result.keys())}")
                    assert False, f"Pivot diagnostics missing: {missing_fields}"
                else:
                    print("  ✓ All diagnostic fields present:")
                    print(f"    - pivot_intermediate: '{result['pivot_intermediate']}'")
                    print(f"    - pivot_intermediate_method: {result['pivot_intermediate_method']}")
                    print(f"    - pivot_final_method: {result['pivot_final_method']}")
                    print(f"    - pivot_stage2_elapsed: {result['pivot_stage2_elapsed']}s")
                    print(f"    - pivot_stage3_elapsed: {result['pivot_stage3_elapsed']}s")
                    print(f"    - pivot_path: {result['pivot_path']}")
            else:
                print(f"  ✗ Pivot NOT used (direct method: {result['translation_method']})")
                
                # Verify diagnostic fields are NOT present when pivot not used
                pivot_fields = [f for f in result.keys() if f.startswith('pivot_')]
                if pivot_fields:
                    print(f"  ✗ WARNING: Pivot fields present when pivot not used: {pivot_fields}")
                else:
                    print("  ✓ No pivot fields (correct - pivot not used)")
        
    finally:
        settings.filipino_pivot_enabled = original_setting


if __name__ == "__main__":
    asyncio.run(test_pivot_diagnostics_populated())
