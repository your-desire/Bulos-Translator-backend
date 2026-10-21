"""
Test Question Pattern Evidence Level Distinction

Verifies that word-level recognition (5 documented question words) is properly
distinguished from sentence-level validation (no documented interrogative sentences).

Test Goal: Ensure "Ànu negayan mu?" recognizes Ànu (word-level) but does NOT
validate the complete sentence structure as grammatically verified.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from services.grammar_rules import initialize_grammar_engine

def test_question_evidence_levels():
    """Test Question pattern evidence level distinction."""
    
    rules_path = Path(__file__).parent / "data" / "grammar_rules.yaml"
    
    if not rules_path.exists():
        print(f"❌ FAIL: Grammar rules file not found at {rules_path}")
        return False
    
    print("=" * 80)
    print("Question Pattern Evidence Level Test")
    print("=" * 80)
    
    # Initialize grammar engine
    grammar_engine = initialize_grammar_engine(rules_path)
    
    # Test cases
    test_cases = [
        {
            "sentence": "Ànu negayan mu?",
            "description": "Question word Ànu with unknown sentence structure",
            "expected_status": "word_recognized",
            "expected_evidence_level": "word",
            "should_match": True
        },
        {
            "sentence": "Dênu ka mapanaw?",
            "description": "Question word Dênu with unknown sentence structure",
            "expected_status": "word_recognized",
            "expected_evidence_level": "word",
            "should_match": True
        },
        {
            "sentence": "kapide negayan mo i bukid?",
            "description": "Question word kapide with unknown sentence structure",
            "expected_status": "word_recognized",
            "expected_evidence_level": "word",
            "should_match": True
        },
        {
            "sentence": "Pidê i bayad?",
            "description": "Question word Pidê with unknown sentence structure",
            "expected_status": "word_recognized",
            "expected_evidence_level": "word",
            "should_match": True
        },
        {
            "sentence": "papalanu magproblema ka?",
            "description": "Question word papalanu with unknown sentence structure",
            "expected_status": "word_recognized",
            "expected_evidence_level": "word",
            "should_match": True
        },
        {
            "sentence": "Masampat i bahay ni Pedro.",
            "description": "Possessive sentence with ni marker (sentence-level evidence)",
            "expected_status": "verified",
            "expected_evidence_level": "sentence",
            "should_match": True
        },
        {
            "sentence": "Si Juan ay mabait.",
            "description": "Topic-Comment with ay marker (sentence-level evidence)",
            "expected_status": "verified",
            "expected_evidence_level": "sentence",
            "should_match": True
        },
        {
            "sentence": "Negayan ako sa tindahan.",
            "description": "No pattern markers - should not match",
            "expected_status": "unverified",
            "expected_evidence_level": None,
            "should_match": False
        }
    ]
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        sentence = test_case["sentence"]
        description = test_case["description"]
        expected_status = test_case["expected_status"]
        expected_level = test_case["expected_evidence_level"]
        should_match = test_case["should_match"]
        
        print(f"\n{'=' * 80}")
        print(f"Test {i}: {description}")
        print(f"Sentence: \"{sentence}\"")
        print(f"Expected Status: {expected_status}")
        print(f"Expected Evidence Level: {expected_level}")
        print(f"{'=' * 80}")
        
        # Validate sentence
        result = grammar_engine.validate_sentence(sentence, source_lang="bul")
        
        # Extract results
        matched = result.get("is_valid", False)
        matched_rules = result.get("matched_rules", [])
        matched_patterns = result.get("matched_patterns", [])
        
        # Determine status based on evidence level
        if matched_patterns:
            has_sentence_level = any(
                p.get("evidence_level") == "sentence"
                for p in matched_patterns
            )
            
            if has_sentence_level:
                actual_status = "verified"
                actual_level = "sentence"
            else:
                actual_status = "word_recognized"
                actual_level = "word"
        else:
            actual_status = "unverified"
            actual_level = None
        
        # Print results
        print(f"\nActual Status: {actual_status}")
        print(f"Actual Evidence Level: {actual_level}")
        print(f"Matched: {matched}")
        print(f"Matched Rules: {matched_rules}")
        
        if matched_patterns:
            print("\nMatched Patterns:")
            for pattern in matched_patterns:
                print(f"  - Rule: {pattern['rule_name']}")
                print(f"    Type: {pattern['pattern_type']}")
                print(f"    Confidence: {pattern['confidence']:.2f}")
                print(f"    Evidence: {pattern['evidence']}")
                print(f"    Evidence Level: {pattern.get('evidence_level', 'N/A')}")
                print(f"    Markers: {pattern.get('markers_found', [])}")
        
        # Verify expectations
        test_passed = True
        
        if matched != should_match:
            print(f"\n❌ FAIL: Expected match={should_match}, got {matched}")
            test_passed = False
        
        if actual_status != expected_status:
            print(f"\n❌ FAIL: Expected status '{expected_status}', got '{actual_status}'")
            test_passed = False
        
        if actual_level != expected_level:
            print(f"\n❌ FAIL: Expected evidence level '{expected_level}', got '{actual_level}'")
            test_passed = False
        
        if test_passed:
            print("\n✅ PASS")
            passed += 1
        else:
            failed += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    print(f"Total Tests: {len(test_cases)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Success Rate: {(passed/len(test_cases)*100):.1f}%")
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Question pattern properly distinguishes word vs sentence evidence")
        return True
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
        return False

def test_translation_service_integration():
    """Test integration with translation service grammar validation."""
    
    print("\n" + "=" * 80)
    print("Translation Service Integration Test")
    print("=" * 80)
    
    from services.translation import TranslationService
    import asyncio
    
    async def run_test():
        service = TranslationService()
        await service.initialize()
        
        # Test question sentence
        print("\nTest: Question word recognition in translation API")
        print("Sentence: 'Ànu negayan mu?'")
        
        # Simulate validation (we're testing the grammar validation logic)
        result = service._validate_with_grammar(
            original="What are you doing?",
            translated="Ànu negayan mu?",
            source_lang="en",
            target_lang="bul"
        )
        
        print(f"\nGrammar Status: {result.get('grammar_status')}")
        print(f"Applied Rule: {result.get('applied_rule')}")
        print(f"Evidence Level: {result.get('evidence_level')}")
        
        # Verify expectations
        expected_status = "word_recognized"
        expected_level = "word"
        
        if result.get("grammar_status") == expected_status and result.get("evidence_level") == expected_level:
            print("\n✅ PASS: Translation service correctly identifies word-level evidence")
            return True
        else:
            print(f"\n❌ FAIL: Expected status='{expected_status}' and level='{expected_level}'")
            print(f"Got status='{result.get('grammar_status')}' and level='{result.get('evidence_level')}'")
            return False
    
    return asyncio.run(run_test())

if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("QUESTION PATTERN EVIDENCE LEVEL DISTINCTION TEST SUITE")
    print("=" * 80)
    print("\nObjective: Verify that Question pattern distinguishes between:")
    print("  1. Word-level recognition: 5 documented question words from WORDS sheet")
    print("  2. Sentence-level validation: Complete interrogative sentence structures")
    print("\nCurrent Evidence:")
    print("  - Question words documented: 5 (Ànu, Dênu, kapide, Pidê, papalanu)")
    print("  - Complete question sentences documented: 0")
    print("\nExpected Behavior:")
    print("  - 'Ànu negayan mu?' → grammar_status='word_recognized', evidence_level='word'")
    print("  - NOT grammar_status='verified' (which would falsely imply sentence validation)")
    print("=" * 80)
    
    # Run tests
    test1_passed = test_question_evidence_levels()
    test2_passed = test_translation_service_integration()
    
    # Overall result
    print("\n" + "=" * 80)
    print("OVERALL TEST RESULT")
    print("=" * 80)
    
    if test1_passed and test2_passed:
        print("✅ ALL TESTS PASSED")
        print("\nVerification Complete:")
        print("  ✓ Question pattern recognizes words without validating sentence structure")
        print("  ✓ Evidence level distinction properly implemented")
        print("  ✓ API responses reflect word-level vs sentence-level evidence")
        print("  ✓ No false validation of undocumented sentence patterns")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
