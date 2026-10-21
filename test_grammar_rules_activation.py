"""
Test script to verify grammar rules are loaded and activated in TranslationService.
Tests all five documented grammar patterns with authentic Bulos examples.
"""
import sys
import asyncio
sys.path.insert(0, '.')

from services.translation import TranslationService
from pathlib import Path
import json

async def test_grammar_rules_activation():
    """Test that all five grammar rules load and work correctly."""
    
    print('=' * 80)
    print('GRAMMAR RULES ACTIVATION TEST')
    print('=' * 80)
    
    # ========================================================================
    # TASK 1: Verify Rules File Exists
    # ========================================================================
    print('\n[TASK 1] Checking Rules File...')
    print('-' * 80)
    
    rules_path = Path('data/grammar_rules.yaml')
    if rules_path.exists():
        print(f'[OK] Rules file found: {rules_path}')
        print(f'  File size: {rules_path.stat().st_size} bytes')
    else:
        print(f'[FAIL] Rules file NOT found: {rules_path}')
        return False
    
    # ========================================================================
    # TASK 2: Initialize TranslationService
    # ========================================================================
    print('\n[TASK 2] Initializing TranslationService...')
    print('-' * 80)
    
    service = TranslationService()
    await service.initialize()
    
    if service.grammar_engine is None:
        print('✗ Grammar engine NOT initialized')
        return False
    
    print('✓ Grammar engine initialized')
    
    # ========================================================================
    # TASK 3: Verify Rules Loaded
    # ========================================================================
    print('\n[TASK 3] Verifying Rules Loaded...')
    print('-' * 80)
    
    stats = service.grammar_engine.get_statistics()
    
    print(f'Statistics:')
    print(f'  Total rules: {stats["total_rules"]}')
    print(f'  Approved rules: {stats["approved_rules"]}')
    print(f'  Validation-enabled: {stats["validation_enabled"]}')
    print(f'  Generation-enabled: {stats["generation_enabled"]}')
    
    if stats['total_rules'] != 5:
        print(f'\n✗ Expected 5 rules, got {stats["total_rules"]}')
        return False
    
    if stats['validation_enabled'] != 5:
        print(f'\n✗ Expected 5 validation-enabled rules, got {stats["validation_enabled"]}')
        return False
    
    if stats['generation_enabled'] != 0:
        print(f'\n✗ Expected 0 generation-enabled rules, got {stats["generation_enabled"]}')
        return False
    
    print('\n✓ All 5 rules loaded correctly')
    print('✓ All 5 rules enabled for validation')
    print('✓ 0 rules enabled for generation (correct)')
    
    # List loaded rules
    print('\nLoaded Rules:')
    for rule_id, rule in service.grammar_engine.rules.items():
        print(f'  • {rule_id}:')
        print(f'    Name: {rule.name}')
        print(f'    Type: {rule.rule_type.value}')
        print(f'    Status: {rule.status.value}')
        print(f'    Can validate: {rule.can_validate()}')
        print(f'    Can generate: {rule.can_generate()}')
    
    # ========================================================================
    # TASK 4: Test Question Pattern Recognition
    # ========================================================================
    print('\n[TASK 4] Testing QUESTION Pattern Recognition...')
    print('-' * 80)
    
    question_tests = [
        {
            'text': 'Ànu i negayan mu?',
            'expected_word': 'Ànu',
            'expected_meaning': 'what',
            'source': 'WORDS sheet, Row 89'
        },
        {
            'text': 'Dênu ka napun?',
            'expected_word': 'Dênu',
            'expected_meaning': 'where',
            'source': 'WORDS sheet, Row 90'
        },
        {
            'text': 'kapide ka datang?',
            'expected_word': 'kapide',
            'expected_meaning': 'when',
            'source': 'WORDS sheet, Row 91'
        },
        {
            'text': 'Pidê i bayu?',
            'expected_word': 'Pidê',
            'expected_meaning': 'how much/how many',
            'source': 'WORDS sheet, Row 92'
        },
        {
            'text': 'papalanu i gegibun mo?',
            'expected_word': 'papalanu',
            'expected_meaning': 'how',
            'source': 'WORDS sheet, Row 93'
        }
    ]
    
    question_passed = 0
    for test in question_tests:
        result = service.grammar_engine.validate_sentence(test['text'])
        matched = 'question_interrogative' in result.get('matched_rules', [])
        
        status = '✓' if matched else '✗'
        print(f'\n{status} "{test["text"]}"')
        print(f'   Question word: {test["expected_word"]} ({test["expected_meaning"]})')
        print(f'   Source: {test["source"]}')
        print(f'   Matched: {matched}')
        print(f'   Confidence: {result.get("validation_confidence", 0):.2f}')
        
        if matched:
            question_passed += 1
            patterns = result.get('matched_patterns', [])
            for p in patterns:
                if p['rule_id'] == 'question_interrogative':
                    print(f'   Evidence: {p.get("evidence", "N/A")}')
                    print(f'   Markers: {p.get("markers_found", [])}')
    
    print(f'\nQuestion Pattern: {question_passed}/5 tests passed')
    
    # ========================================================================
    # TASK 5: Test Topic-Comment Pattern
    # ========================================================================
    print('\n[TASK 5] Testing TOPIC-COMMENT Pattern Recognition...')
    print('-' * 80)
    
    topic_comment_tests = [
        {
            'text': 'Ikitam ay Magsolat',
            'source': 'SENTENCES sheet, Row 3',
            'english': 'Let us Read and Write'
        },
        {
            'text': 'I Surot a Dumaget Bulos ay te dalawampu',
            'source': 'SENTENCES sheet, Row 6 (shortened)',
            'english': 'The Dumaget Bulos Language has twenty...'
        },
        {
            'text': 'I tetik e ay te aduwa a tinug',
            'source': 'SENTENCES sheet, Row 17 (shortened)',
            'english': 'Letter e has two sounds'
        }
    ]
    
    topic_comment_passed = 0
    for test in topic_comment_tests:
        result = service.grammar_engine.validate_sentence(test['text'])
        matched = 'topic_comment' in result.get('matched_rules', [])
        
        status = '✓' if matched else '✗'
        print(f'\n{status} "{test["text"]}"')
        print(f'   Source: {test["source"]}')
        print(f'   English: {test["english"]}')
        print(f'   Matched: {matched}')
        print(f'   Confidence: {result.get("validation_confidence", 0):.2f}')
        
        if matched:
            topic_comment_passed += 1
    
    print(f'\nTopic-Comment Pattern: {topic_comment_passed}/3 tests passed')
    
    # ========================================================================
    # TASK 6: Test Possessive Pattern
    # ========================================================================
    print('\n[TASK 6] Testing POSSESSIVE Pattern Recognition...')
    print('-' * 80)
    
    possessive_tests = [
        {
            'text': 'I beloy ni Juan',
            'markers': ['ni'],
            'english': 'The house of Juan'
        },
        {
            'text': 'I pagsolat de Bulos',
            'markers': ['de'],
            'english': 'The writing of Bulos'
        },
        {
            'text': 'I libro na Pedro',
            'markers': ['na'],
            'english': 'The book of Pedro'
        }
    ]
    
    possessive_passed = 0
    for test in possessive_tests:
        result = service.grammar_engine.validate_sentence(test['text'])
        matched = 'possessive' in result.get('matched_rules', [])
        
        status = '✓' if matched else '✗'
        print(f'\n{status} "{test["text"]}"')
        print(f'   Markers: {test["markers"]}')
        print(f'   English: {test["english"]}')
        print(f'   Matched: {matched}')
        print(f'   Confidence: {result.get("validation_confidence", 0):.2f}')
        
        if matched:
            possessive_passed += 1
    
    print(f'\nPossessive Pattern: {possessive_passed}/3 tests passed')
    
    # ========================================================================
    # TASK 7: Test Predicate-Adjective Pattern
    # ========================================================================
    print('\n[TASK 7] Testing PREDICATE-ADJECTIVE Pattern Recognition...')
    print('-' * 80)
    
    pred_adj_tests = [
        {
            'text': 'Malawwa i beloy',
            'english': 'Big house'
        },
        {
            'text': 'Bowon i tao',
            'english': 'Good person'
        },
        {
            'text': 'Masampat i kabayo',
            'english': 'Fast horse'
        }
    ]
    
    pred_adj_passed = 0
    for test in pred_adj_tests:
        result = service.grammar_engine.validate_sentence(test['text'])
        matched = 'predicate_adjective' in result.get('matched_rules', [])
        
        status = '✓' if matched else '✗'
        print(f'\n{status} "{test["text"]}"')
        print(f'   English: {test["english"]}')
        print(f'   Matched: {matched}')
        print(f'   Confidence: {result.get("validation_confidence", 0):.2f}')
        
        if matched:
            pred_adj_passed += 1
    
    print(f'\nPredicate-Adjective Pattern: {pred_adj_passed}/3 tests passed')
    
    # ========================================================================
    # TASK 8: Test Imperative Pattern
    # ========================================================================
    print('\n[TASK 8] Testing IMPERATIVE Pattern Recognition...')
    print('-' * 80)
    
    imperative_tests = [
        {
            'text': 'Amitin tam un ikan',
            'source': 'SENTENCES sheet, Row 156',
            'english': 'Let us get the fish'
        },
        {
            'text': 'Dian tam ni kolay un larawen',
            'source': 'SENTENCES sheet, Row 157',
            'english': 'Let us color the picture'
        },
        {
            'text': 'Biyen tam ni sinaing un manganak',
            'source': 'SENTENCES sheet, Row 158',
            'english': 'Let us give rice to the children'
        }
    ]
    
    imperative_passed = 0
    for test in imperative_tests:
        result = service.grammar_engine.validate_sentence(test['text'])
        matched = 'imperative' in result.get('matched_rules', [])
        
        status = '✓' if matched else '✗'
        print(f'\n{status} "{test["text"]}"')
        print(f'   Source: {test["source"]}')
        print(f'   English: {test["english"]}')
        print(f'   Matched: {matched}')
        print(f'   Confidence: {result.get("validation_confidence", 0):.2f}')
        
        if matched:
            imperative_passed += 1
    
    print(f'\nImperative Pattern: {imperative_passed}/3 tests passed')
    
    # ========================================================================
    # TASK 9: Test Non-Matching Inputs
    # ========================================================================
    print('\n[TASK 9] Testing Non-Matching Inputs...')
    print('-' * 80)
    
    non_matching_tests = [
        'Random English text',
        'Simple Bulos word without pattern',
        '12345'
    ]
    
    false_positives = 0
    for test_text in non_matching_tests:
        result = service.grammar_engine.validate_sentence(test_text)
        matched = result.get('is_valid', False)
        
        if matched:
            false_positives += 1
            print(f'✗ FALSE POSITIVE: "{test_text}" matched incorrectly')
            print(f'   Matched rules: {result.get("matched_rules", [])}')
        else:
            print(f'✓ "{test_text}" correctly not matched')
    
    print(f'\nFalse Positives: {false_positives}/3')
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print('\n' + '=' * 80)
    print('TEST SUMMARY')
    print('=' * 80)
    
    total_tests = question_passed + topic_comment_passed + possessive_passed + pred_adj_passed + imperative_passed
    total_expected = 5 + 3 + 3 + 3 + 3  # 17 total tests
    
    print(f'\nPattern Recognition Results:')
    print(f'  Question:           {question_passed}/5 passed')
    print(f'  Topic-Comment:      {topic_comment_passed}/3 passed')
    print(f'  Possessive:         {possessive_passed}/3 passed')
    print(f'  Predicate-Adjective: {pred_adj_passed}/3 passed')
    print(f'  Imperative:         {imperative_passed}/3 passed')
    print(f'\nTotal: {total_tests}/{total_expected} tests passed')
    print(f'False Positives: {false_positives}')
    
    success_rate = (total_tests / total_expected) * 100
    print(f'\nSuccess Rate: {success_rate:.1f}%')
    
    if total_tests == total_expected and false_positives == 0:
        print('\n✓✓✓ ALL TESTS PASSED ✓✓✓')
        print('Grammar rules are correctly loaded and activated!')
        return True
    else:
        print('\n⚠️  SOME TESTS FAILED')
        print('Review pattern matching logic or rules configuration.')
        return False

if __name__ == '__main__':
    success = asyncio.run(test_grammar_rules_activation())
    sys.exit(0 if success else 1)
