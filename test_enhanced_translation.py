"""
Test enhanced translation with corpus-grounded retrieval.
"""

import asyncio
from services.translation import TranslationService


async def test():
    print("=" * 70)
    print("ENHANCED TRANSLATION TEST")
    print("=" * 70)
    
    service = TranslationService()
    await service.initialize()
    
    # Test cases: documented sentences from corpus
    test_cases = [
        {
            "name": "Documented complete sentence (BUL→EN)",
            "text": "Ànu i ngalan mu?",
            "source": "bul",
            "target": "en",
            "expected_method": "phrase_match",
            "expected_translation": "What is your name?",
        },
        {
            "name": "Documented complete sentence (BUL→TL)",
            "text": "Malawwa i kalasan",
            "source": "bul",
            "target": "tl",
            "expected_method": "phrase_match",
            "note": "Should find in sentence annotations"
        },
        {
            "name": "Multi-word documented phrase",
            "text": "I Surot a Dumaget Bulos",
            "source": "bul",
            "target": "en",
            "note": "Should match documented phrase"
        },
        {
            "name": "Single word from dictionary",
            "text": "ulù",
            "source": "bul",
            "target": "en",
            "expected_method": "phrase_match",
            "expected_translation": "head",
        },
        {
            "name": "Word combination",
            "text": "malaki bahay",
            "source": "bul",
            "target": "en",
            "note": "Should use word matching"
        },
    ]
    
    print("\n" + "-" * 70)
    print("TRANSLATION ENHANCEMENT TESTS")
    print("-" * 70)
    
    for test in test_cases:
        print(f"\n[TEST] {test['name']}")
        print(f"       Input: '{test['text']}' ({test['source']}→{test['target']})")
        
        result = await service.translate(
            test['text'],
            test['source'],
            test['target']
        )
        
        print(f"       Translated: '{result['translated_text']}'")
        print(f"       Method: {result['translation_method']}")
        print(f"       Confidence: {result['confidence']}")
        print(f"       Grammar Status: {result.get('grammar_status', 'N/A')}")
        
        if 'expected_translation' in test:
            if result['translated_text'] == test['expected_translation']:
                print(f"       ✅ Translation matches expected")
            else:
                print(f"       ⚠️  Expected: '{test['expected_translation']}'")
        
        if 'expected_method' in test:
            if result['translation_method'] == test['expected_method']:
                print(f"       ✅ Method matches expected")
            else:
                print(f"       ⚠️  Expected method: {test['expected_method']}")
        
        if 'note' in test:
            print(f"       Note: {test['note']}")
    
    print("\n" + "=" * 70)
    print("ENHANCEMENT TEST COMPLETE")
    print("=" * 70)
    
    print("\n📋 ENHANCEMENTS:")
    print("   • Enhanced _lookup_phrase() with sentence annotation fallback")
    print("   • Corpus-grounded phrase matching for documented translations")
    print("   • Source references logged for corpus matches")
    print("   • Greedy longest-match word matching (already implemented)")
    print("   • POS annotations available for future improvements")


if __name__ == "__main__":
    asyncio.run(test())
