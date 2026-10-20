"""
Day 6: Comprehensive Direct vs Pivot Translation Evaluation

Tests 5 evaluation groups as specified:
A. Exact documented sentence translations
B. Unseen sentence combinations
C. Direct translation failures
D. Ambiguous and unsupported inputs
E. Inputs where controlled pivoting is eligible

Tests both EN→TL→BUL and BUL→TL→EN where supported.
Evaluates with pivot disabled and enabled.
No fabricated Bulos translations - only documented dataset entries.
"""

import asyncio
import json
from typing import Dict, List, Any
from services.translation import TranslationService
from config import settings


class Day6Evaluator:
    """Comprehensive evaluation comparing direct vs pivot translation."""
    
    def __init__(self):
        self.results = {
            'group_a': {'direct': [], 'pivot': []},
            'group_b': {'direct': [], 'pivot': []},
            'group_c': {'direct': [], 'pivot': []},
            'group_d': {'direct': [], 'pivot': []},
            'group_e': {'direct': [], 'pivot': []}
        }
    
    async def run_evaluation(self):
        """Execute all evaluation groups."""
        print("="*80)
        print(" DAY 6: COMPREHENSIVE DIRECT VS PIVOT TRANSLATION EVALUATION")
        print("="*80)
        print("\nEvaluation Groups:")
        print("  A. Exact documented sentence translations")
        print("  B. Unseen sentence combinations")
        print("  C. Direct translation failures")
        print("  D. Ambiguous and unsupported inputs")
        print("  E. Inputs where controlled pivoting is eligible")
        print("\n" + "="*80)
        
        # Load dataset for reference
        with open('sentence.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.dataset = data.get('entries', [])
        
        await self.evaluate_group_a()
        await self.evaluate_group_b()
        await self.evaluate_group_c()
        await self.evaluate_group_d()
        await self.evaluate_group_e()
        
        self.save_results()
        self.print_summary()
    
    async def evaluate_group_a(self):
        """
        Group A: Exact documented sentence translations.
        
        These are phrases that exist verbatim in sentence.json.
        Expected: Direct translation succeeds with phrase_match.
        Pivot should NOT be attempted (direct is good).
        """
        print("\n" + "="*80)
        print(" GROUP A: Exact Documented Sentence Translations")
        print("="*80)
        
        # Select diverse documented phrases from dataset
        test_cases = [
            {
                'bul': 'Tuntonin',
                'en': 'Rule',
                'tl': 'Tuntunin',
                'description': 'Single word - Rule'
            },
            {
                'bul': 'Ikitam ay Magsolat',
                'en': 'Let us Read and Write',
                'tl': 'Magbasa at Sumulat Tayo',
                'description': 'Simple sentence - education'
            },
            {
                'bul': 'Ay! Ti bebek!',
                'en': 'Hey! Snake!',
                'tl': 'Hoy! Ahas!',
                'description': 'Exclamation - warning'
            },
            {
                'bul': 'I kambal-katenig',
                'en': 'Consonant Cluster',
                'tl': 'Ang kambal-katinig',
                'description': 'Linguistic term'
            },
            {
                'bul': 'Lugel',
                'en': 'Place',
                'tl': 'Lugar',
                'description': 'Single word - Place'
            }
        ]
        
        for case in test_cases:
            print(f"\n{case['description']}")
            print(f"  BUL: '{case['bul']}' | EN: '{case['en']}' | TL: '{case['tl']}'")
            
            # Test BUL→EN
            await self._test_pair(
                case['bul'], 'bul', 'en', case['en'],
                'group_a', f"{case['description']} (BUL→EN)"
            )
            
            # Test EN→BUL
            await self._test_pair(
                case['en'], 'en', 'bul', case['bul'],
                'group_a', f"{case['description']} (EN→BUL)"
            )
            
            # Test BUL→TL
            await self._test_pair(
                case['bul'], 'bul', 'tl', case['tl'],
                'group_a', f"{case['description']} (BUL→TL)"
            )
    
    async def evaluate_group_b(self):
        """
        Group B: Unseen sentence combinations.
        
        Valid Bulos words combined in ways not present in sentence.json.
        Expected: May fail direct (no phrase_match), pivot might help.
        """
        print("\n" + "="*80)
        print(" GROUP B: Unseen Sentence Combinations")
        print("="*80)
        
        # Phrases constructed from known words but not in dataset
        test_cases = [
            {
                'text': 'Lugel na',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Place + particle (unseen combination)',
                'reference': None  # No known reference translation
            },
            {
                'text': 'I Pasko ay masampat',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Christmas + is beautiful (combination)',
                'reference': None
            },
            {
                'text': 'Tuntonin ni pagsolat',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Rule + of writing (combination)',
                'reference': None
            }
        ]
        
        for case in test_cases:
            print(f"\n{case['description']}")
            print(f"  Input: '{case['text']}' ({case['src']}→{case['tgt']})")
            
            await self._test_pair(
                case['text'], case['src'], case['tgt'], case.get('reference'),
                'group_b', case['description']
            )
    
    async def evaluate_group_c(self):
        """
        Group C: Direct translation failures.
        
        Inputs that fail all direct translation steps (phrase, word, fuzzy, LSTM).
        Expected: Direct returns no_match or very low confidence.
        Pivot is the last resort.
        """
        print("\n" + "="*80)
        print(" GROUP C: Direct Translation Failures")
        print("="*80)
        
        test_cases = [
            {
                'text': 'xyzabc',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Nonsense text (complete failure)',
                'reference': None
            },
            {
                'text': 'qwerty keyboard',
                'src': 'en',
                'tgt': 'bul',
                'description': 'Modern tech terms (not in dataset)',
                'reference': None
            },
            {
                'text': '123 456',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Numbers only',
                'reference': None
            }
        ]
        
        for case in test_cases:
            print(f"\n{case['description']}")
            print(f"  Input: '{case['text']}' ({case['src']}→{case['tgt']})")
            
            await self._test_pair(
                case['text'], case['src'], case['tgt'], case.get('reference'),
                'group_c', case['description']
            )
    
    async def evaluate_group_d(self):
        """
        Group D: Ambiguous and unsupported inputs.
        
        Edge cases: empty strings, very long text, mixed languages, special chars.
        Expected: Should handle gracefully without crashing.
        """
        print("\n" + "="*80)
        print(" GROUP D: Ambiguous and Unsupported Inputs")
        print("="*80)
        
        test_cases = [
            {
                'text': '',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Empty string',
                'reference': None
            },
            {
                'text': '   ',
                'src': 'en',
                'tgt': 'bul',
                'description': 'Whitespace only',
                'reference': None
            },
            {
                'text': 'hello مرحبا',
                'src': 'en',
                'tgt': 'bul',
                'description': 'Mixed English-Arabic',
                'reference': None
            },
            {
                'text': '!!!',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Special characters only',
                'reference': None
            }
        ]
        
        for case in test_cases:
            print(f"\n{case['description']}")
            print(f"  Input: '{case['text']}' ({case['src']}→{case['tgt']})")
            
            await self._test_pair(
                case['text'], case['src'], case['tgt'], case.get('reference'),
                'group_d', case['description']
            )
    
    async def evaluate_group_e(self):
        """
        Group E: Inputs where controlled pivoting is eligible.
        
        Cases where:
        - Direct translation produces low-quality result (fuzzy_match_partial)
        - BUL↔TL mapping exists in dataset
        - Pivot path could improve quality
        
        Expected: Pivot might be attempted and could improve result.
        """
        print("\n" + "="*80)
        print(" GROUP E: Eligible Pivot Candidates")
        print("="*80)
        
        # Find phrases that exist in BUL-TL but maybe not BUL-EN
        bul_tl_pairs = [
            (x['BULOS'], x['FILIPINO']) 
            for x in self.dataset 
            if x.get('BULOS') and x.get('FILIPINO')
        ]
        
        test_cases = [
            {
                'text': 'Ikitam ay Magsolat',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Known BUL-TL pair (Let us read and write)',
                'reference': 'Let us Read and Write',
                'bul_tl_exists': True
            },
            {
                'text': 'Masampat i Dapis',
                'src': 'bul',
                'tgt': 'en',
                'description': 'Known BUL-TL pair (Dapis is beautiful)',
                'reference': 'Dapis is beautiful',
                'bul_tl_exists': True
            }
        ]
        
        for case in test_cases:
            print(f"\n{case['description']}")
            print(f"  Input: '{case['text']}' ({case['src']}→{case['tgt']})")
            print(f"  BUL↔TL mapping exists: {case['bul_tl_exists']}")
            
            await self._test_pair(
                case['text'], case['src'], case['tgt'], case.get('reference'),
                'group_e', case['description']
            )
    
    async def _test_pair(
        self, 
        text: str, 
        src: str, 
        tgt: str, 
        reference: str,
        group: str,
        description: str
    ):
        """
        Test a translation pair with pivot disabled and enabled.
        
        Args:
            text: Source text
            src: Source language
            tgt: Target language
            reference: Expected translation (None if unknown)
            group: Evaluation group (group_a, group_b, etc.)
            description: Test case description
        """
        # Test with pivot DISABLED
        settings.filipino_pivot_enabled = False
        service_direct = TranslationService()
        await service_direct.initialize()
        
        try:
            direct_result = await service_direct.translate(text, src, tgt)
            direct_data = {
                'description': description,
                'input': text,
                'src': src,
                'tgt': tgt,
                'reference': reference,
                'output': direct_result['translated_text'],
                'method': direct_result['translation_method'],
                'confidence': direct_result.get('confidence', 0.0),
                'exact_match': (
                    direct_result['translated_text'].lower() == reference.lower() 
                    if reference else None
                ),
                'error': None
            }
            print(f"    Direct:  '{direct_result['translated_text']}' "
                  f"({direct_result['translation_method']}, "
                  f"conf={direct_result.get('confidence', 0.0):.2f})")
        except Exception as e:
            direct_data = {
                'description': description,
                'input': text,
                'src': src,
                'tgt': tgt,
                'reference': reference,
                'output': None,
                'method': 'error',
                'confidence': 0.0,
                'exact_match': False,
                'error': str(e)
            }
            print(f"    Direct:  ERROR - {e}")
        
        self.results[group]['direct'].append(direct_data)
        
        # Test with pivot ENABLED
        settings.filipino_pivot_enabled = True
        service_pivot = TranslationService()
        await service_pivot.initialize()
        
        try:
            pivot_result = await service_pivot.translate(text, src, tgt)
            pivot_used = pivot_result['translation_method'].startswith('filipino_pivot')
            
            pivot_data = {
                'description': description,
                'input': text,
                'src': src,
                'tgt': tgt,
                'reference': reference,
                'output': pivot_result['translated_text'],
                'method': pivot_result['translation_method'],
                'confidence': pivot_result.get('confidence', 0.0),
                'exact_match': (
                    pivot_result['translated_text'].lower() == reference.lower() 
                    if reference else None
                ),
                'pivot_used': pivot_used,
                'pivot_intermediate': pivot_result.get('pivot_intermediate'),
                'pivot_path': pivot_result.get('pivot_path'),
                'error': None
            }
            
            pivot_marker = " [PIVOT]" if pivot_used else ""
            print(f"    Pivot:   '{pivot_result['translated_text']}' "
                  f"({pivot_result['translation_method']}, "
                  f"conf={pivot_result.get('confidence', 0.0):.2f}){pivot_marker}")
            
            if pivot_used and pivot_result.get('pivot_intermediate'):
                print(f"      └→ via: '{pivot_result['pivot_intermediate']}' "
                      f"({pivot_result.get('pivot_path', [])})")
        except Exception as e:
            pivot_data = {
                'description': description,
                'input': text,
                'src': src,
                'tgt': tgt,
                'reference': reference,
                'output': None,
                'method': 'error',
                'confidence': 0.0,
                'exact_match': False,
                'pivot_used': False,
                'error': str(e)
            }
            print(f"    Pivot:   ERROR - {e}")
        
        self.results[group]['pivot'].append(pivot_data)
        
        # Comparison
        if reference:
            if direct_data['exact_match'] and pivot_data['exact_match']:
                print(f"    ✓ Both match reference")
            elif direct_data['exact_match']:
                print(f"    ⚠ Direct matches, pivot doesn't")
            elif pivot_data['exact_match']:
                print(f"    ✓ Pivot matches reference (direct didn't)")
            else:
                print(f"    ✗ Neither matches reference")
        
        # Reset to default
        settings.filipino_pivot_enabled = False
    
    def save_results(self):
        """Save detailed results to JSON file."""
        output = {
            'evaluation_date': '2026-10-17',
            'total_tests': sum(
                len(self.results[g]['direct']) for g in self.results
            ),
            'groups': self.results,
            'summary': self._calculate_summary()
        }
        
        with open('document/DAY6_EVALUATION_RESULTS.json', 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*80)
        print(" Results saved to: document/DAY6_EVALUATION_RESULTS.json")
        print("="*80)
    
    def _calculate_summary(self) -> Dict[str, Any]:
        """Calculate summary statistics across all groups."""
        summary = {}
        
        for group_name, group_data in self.results.items():
            direct = group_data['direct']
            pivot = group_data['pivot']
            
            summary[group_name] = {
                'total_tests': len(direct),
                'direct': {
                    'usable': sum(1 for r in direct if r['confidence'] > 0),
                    'exact_matches': sum(1 for r in direct if r.get('exact_match') is True),
                    'errors': sum(1 for r in direct if r.get('error'))
                },
                'pivot': {
                    'usable': sum(1 for r in pivot if r['confidence'] > 0),
                    'exact_matches': sum(1 for r in pivot if r.get('exact_match') is True),
                    'pivot_used': sum(1 for r in pivot if r.get('pivot_used')),
                    'errors': sum(1 for r in pivot if r.get('error'))
                }
            }
        
        return summary
    
    def print_summary(self):
        """Print evaluation summary."""
        print("\n" + "="*80)
        print(" EVALUATION SUMMARY")
        print("="*80)
        
        summary = self._calculate_summary()
        
        for group_name, stats in summary.items():
            group_label = {
                'group_a': 'Group A: Documented Translations',
                'group_b': 'Group B: Unseen Combinations',
                'group_c': 'Group C: Direct Failures',
                'group_d': 'Group D: Ambiguous Inputs',
                'group_e': 'Group E: Pivot Candidates'
            }.get(group_name, group_name)
            
            print(f"\n{group_label} ({stats['total_tests']} tests)")
            print(f"  Direct:  {stats['direct']['usable']}/{stats['total_tests']} usable, "
                  f"{stats['direct']['exact_matches']} exact matches")
            print(f"  Pivot:   {stats['pivot']['usable']}/{stats['total_tests']} usable, "
                  f"{stats['pivot']['exact_matches']} exact matches, "
                  f"{stats['pivot']['pivot_used']} pivot attempts")


async def main():
    """Run comprehensive evaluation."""
    evaluator = Day6Evaluator()
    await evaluator.run_evaluation()


if __name__ == "__main__":
    asyncio.run(main())
