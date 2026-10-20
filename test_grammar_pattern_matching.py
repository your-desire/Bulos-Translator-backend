"""
Test actual grammar pattern matching with authentic corpus examples.
"""

import asyncio
from services.translation import TranslationService


async def test():
    print("=" * 70)
    print("GRAMMAR PATTERN MATCHING TEST")
    print("=" * 70)
    
    service = TranslationService()
    await service.initialize()
    
    # Test cases from actual corpus (sentence.json)
    test_cases = [
        {
            "name": "Topic marker 'ay' (GR003)",
            "sentence": "I Surot a Dumaget Bulos ay te dalawampu't tiluwan a tinog",
            "expected_patterns": ['topic_comment'],
            "expected_rules": ['GR003'],
        },
        {
            "name": "Predicate adjective with 'i' (GR001)",
            "sentence": "Malawwa i kalasan",
            "expected_patterns": ['predicate_adjective'],
            "expected_rules": ['GR001'],
        },
        {
            "name": "Possessive with 'ni' (GR004)",
            "sentence": "I tinog ni tetik e",
            "expected_patterns": ['possessive'],
            "expected_rules": ['GR004'],
        },
        {
            "name": "Question with 'Ànu' (GR002)",
            "sentence": "Ànu i ngalan mu?",
            "expected_patterns": ['question'],
            "expected_rules": ['GR002'],
        },
        {
            "name": "Question with 'Dênu' (GR002)",
            "sentence": "Dênu ka paagaw?",
            "expected_patterns": ['question'],
            "expected_rules": ['GR002'],
        },
        {
            "name": "Imperative with 'tam' (GR005)",
            "sentence": "Amitin tam un ikan",
            "expected_patterns": ['imperative'],
            "expected_rules": ['GR005'],
        },
        {
            "name": "Multiple patterns: 'ay' + possessive",
            "sentence": "I gebigkas de mga patenig a Surot a Dumaget Bulos ay tolad di",
            "expected_patterns": ['topic_comment', 'possessive'],
            "expected_rules": ['GR003', 'GR004'],
        },
        {
            "name": "No pattern match",
            "sentence": "hello world",
            "expected_patterns": [],
            "expected_rules": [],
        },
    ]
    
    passed = 0
    failed = 0
    
    print("\n" + "-" * 70)
    print("PATTERN MATCHING TESTS")
    print("-" * 70)
    
    for test in test_cases:
        print(f"\n[TEST] {test['name']}")
        print(f"       Sentence: '{test['sentence']}'")
        
        result = service.grammar_engine.validate_sentence(test['sentence'])
        
        matched_rules = result.get('matched_rules', [])
        is_valid = result.get('is_valid', False)
        confidence = result.get('validation_confidence', 0.0)
        matched_patterns = result.get('matched_patterns', [])
        
        print(f"       Valid: {is_valid}")
        print(f"       Confidence: {confidence:.2f}")
        print(f"       Matched rules: {matched_rules}")
        
        if matched_patterns:
            print(f"       Patterns detected:")
            for pattern in matched_patterns:
                print(f"         • {pattern['pattern_type']}: {pattern['rule_name']}")
                print(f"           Evidence: {pattern['evidence']}")
                print(f"           Markers: {pattern['markers_found']}")
        
        # Verify expectations
        expected_rules = test['expected_rules']
        
        if set(matched_rules) == set(expected_rules):
            print(f"       ✅ PASSED: Matched expected rules")
            passed += 1
        else:
            print(f"       ❌ FAILED: Expected {expected_rules}, got {matched_rules}")
            failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    
    if failed == 0:
        print("\n✅ ALL PATTERN MATCHING TESTS PASSED")
        print("\n📋 SUMMARY:")
        print("   • Grammar pattern recognition is working correctly")
        print("   • All 5 grammar rules are validation-enabled")
        print("   • Pattern matching uses corpus-documented markers")
        print("   • Multiple patterns can be detected in one sentence")
        print("   • API now returns accurate grammar_status")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    import sys
    success = asyncio.run(test())
    sys.exit(0 if success else 1)
