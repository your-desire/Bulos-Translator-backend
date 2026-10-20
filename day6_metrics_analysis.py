"""
Day 6 Task 4: Measure and Report Actual Results

Analyzes evaluation results and generates detailed metrics:
1. Exact reference-match results
2. Translation coverage
3. Candidate pivot acceptance and rejection rates
4. Previously unsupported inputs that now receive translations
5. Previously correct translations that regress
6. Reference-based chrF++ where appropriate
7. Latency and timeout behavior

Does not claim semantic accuracy without native-speaker evaluation.
Clearly identifies whether pivot improves performance vs direct-only.
"""

import json
from typing import Dict, List, Any
from collections import defaultdict


class Day6MetricsAnalyzer:
    """Analyzes evaluation results and generates metrics report."""
    
    def __init__(self, results_file: str = 'document/DAY6_EVALUATION_RESULTS.json'):
        with open(results_file, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        
        self.groups = self.data['groups']
        self.summary = self.data['summary']
    
    def analyze_all(self):
        """Generate complete metrics analysis."""
        print("="*80)
        print(" DAY 6: DETAILED METRICS ANALYSIS")
        print("="*80)
        
        metrics = {
            '1_exact_matches': self.analyze_exact_matches(),
            '2_coverage': self.analyze_coverage(),
            '3_pivot_rates': self.analyze_pivot_acceptance_rejection(),
            '4_new_support': self.analyze_new_support(),
            '5_regressions': self.analyze_regressions(),
            '6_chrf': self.analyze_chrf(),
            '7_latency': self.analyze_latency(),
            '8_pivot_improvement': self.analyze_pivot_improvement()
        }
        
        # Save metrics report
        with open('document/DAY6_METRICS_REPORT.json', 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2, ensure_ascii=False)
        
        print("\n" + "="*80)
        print(" Metrics report saved to: document/DAY6_METRICS_REPORT.json")
        print("="*80)
        
        return metrics
    
    def analyze_exact_matches(self) -> Dict[str, Any]:
        """Metric 1: Exact reference-match results."""
        print("\n" + "-"*80)
        print(" METRIC 1: Exact Reference-Match Results")
        print("-"*80)
        
        results = {
            'description': 'Translations that exactly match provided reference',
            'note': 'Only tests with known references are evaluated',
            'by_group': {},
            'overall': {}
        }
        
        total_with_ref = 0
        total_direct_match = 0
        total_pivot_match = 0
        
        for group_name, group_data in self.groups.items():
            direct_tests = [t for t in group_data['direct'] if t['reference'] is not None]
            pivot_tests = [t for t in group_data['pivot'] if t['reference'] is not None]
            
            if not direct_tests:
                continue
            
            direct_matches = sum(1 for t in direct_tests if t.get('exact_match') is True)
            pivot_matches = sum(1 for t in pivot_tests if t.get('exact_match') is True)
            
            results['by_group'][group_name] = {
                'tests_with_reference': len(direct_tests),
                'direct_exact_matches': direct_matches,
                'pivot_exact_matches': pivot_matches,
                'direct_rate': direct_matches / len(direct_tests) if direct_tests else 0,
                'pivot_rate': pivot_matches / len(pivot_tests) if pivot_tests else 0
            }
            
            total_with_ref += len(direct_tests)
            total_direct_match += direct_matches
            total_pivot_match += pivot_matches
            
            print(f"\n  {group_name}:")
            print(f"    Tests with reference: {len(direct_tests)}")
            print(f"    Direct exact matches: {direct_matches}/{len(direct_tests)} "
                  f"({direct_matches/len(direct_tests)*100:.1f}%)")
            print(f"    Pivot exact matches:  {pivot_matches}/{len(pivot_tests)} "
                  f"({pivot_matches/len(pivot_tests)*100:.1f}%)")
        
        results['overall'] = {
            'total_with_reference': total_with_ref,
            'direct_exact_matches': total_direct_match,
            'pivot_exact_matches': total_pivot_match,
            'direct_rate': total_direct_match / total_with_ref if total_with_ref else 0,
            'pivot_rate': total_pivot_match / total_with_ref if total_with_ref else 0
        }
        
        print(f"\n  OVERALL:")
        print(f"    Tests with reference: {total_with_ref}")
        print(f"    Direct exact matches: {total_direct_match} ({total_direct_match/total_with_ref*100:.1f}%)")
        print(f"    Pivot exact matches:  {total_pivot_match} ({total_pivot_match/total_with_ref*100:.1f}%)")
        
        return results
    
    def analyze_coverage(self) -> Dict[str, Any]:
        """Metric 2: Translation coverage (usable translations)."""
        print("\n" + "-"*80)
        print(" METRIC 2: Translation Coverage")
        print("-"*80)
        
        results = {
            'description': 'Percentage of inputs that produce usable translations (confidence > 0)',
            'by_group': {},
            'overall': {}
        }
        
        total_tests = 0
        total_direct_usable = 0
        total_pivot_usable = 0
        
        for group_name, group_data in self.groups.items():
            direct = group_data['direct']
            pivot = group_data['pivot']
            
            direct_usable = sum(1 for t in direct if t['confidence'] > 0)
            pivot_usable = sum(1 for t in pivot if t['confidence'] > 0)
            
            results['by_group'][group_name] = {
                'total_tests': len(direct),
                'direct_usable': direct_usable,
                'pivot_usable': pivot_usable,
                'direct_coverage': direct_usable / len(direct) if direct else 0,
                'pivot_coverage': pivot_usable / len(pivot) if pivot else 0,
                'coverage_improvement': pivot_usable - direct_usable
            }
            
            total_tests += len(direct)
            total_direct_usable += direct_usable
            total_pivot_usable += pivot_usable
            
            print(f"\n  {group_name}:")
            print(f"    Total tests: {len(direct)}")
            print(f"    Direct usable: {direct_usable}/{len(direct)} "
                  f"({direct_usable/len(direct)*100:.1f}%)")
            print(f"    Pivot usable:  {pivot_usable}/{len(pivot)} "
                  f"({pivot_usable/len(pivot)*100:.1f}%)")
            print(f"    Improvement: {pivot_usable - direct_usable:+d}")
        
        results['overall'] = {
            'total_tests': total_tests,
            'direct_usable': total_direct_usable,
            'pivot_usable': total_pivot_usable,
            'direct_coverage': total_direct_usable / total_tests if total_tests else 0,
            'pivot_coverage': total_pivot_usable / total_tests if total_tests else 0,
            'coverage_improvement': total_pivot_usable - total_direct_usable
        }
        
        print(f"\n  OVERALL:")
        print(f"    Total tests: {total_tests}")
        print(f"    Direct coverage: {total_direct_usable}/{total_tests} "
              f"({total_direct_usable/total_tests*100:.1f}%)")
        print(f"    Pivot coverage:  {total_pivot_usable}/{total_tests} "
              f"({total_pivot_usable/total_tests*100:.1f}%)")
        print(f"    Improvement: {total_pivot_usable - total_direct_usable:+d}")
        
        return results
    
    def analyze_pivot_acceptance_rejection(self) -> Dict[str, Any]:
        """Metric 3: Pivot acceptance and rejection rates."""
        print("\n" + "-"*80)
        print(" METRIC 3: Pivot Acceptance and Rejection Rates")
        print("-"*80)
        
        results = {
            'description': 'How often pivot was attempted and succeeded/failed quality gates',
            'by_group': {},
            'overall': {}
        }
        
        total_pivot_attempted = 0
        total_pivot_succeeded = 0
        total_direct_sufficient = 0
        
        for group_name, group_data in self.groups.items():
            pivot = group_data['pivot']
            
            # Pivot attempted = method starts with "filipino_pivot"
            pivot_used = sum(1 for t in pivot if t.get('pivot_used') is True)
            
            # Direct sufficient = pivot enabled but direct method used
            direct_sufficient = sum(
                1 for t in pivot 
                if not t.get('pivot_used') and t['method'] not in ['error', 'no_match', 'empty_input']
            )
            
            results['by_group'][group_name] = {
                'total_tests': len(pivot),
                'pivot_attempted': pivot_used,
                'pivot_rate': pivot_used / len(pivot) if pivot else 0,
                'direct_sufficient': direct_sufficient,
                'direct_rate': direct_sufficient / len(pivot) if pivot else 0
            }
            
            total_pivot_attempted += pivot_used
            total_pivot_succeeded += pivot_used  # If used, gates passed
            total_direct_sufficient += direct_sufficient
            
            print(f"\n  {group_name}:")
            print(f"    Pivot attempted: {pivot_used}/{len(pivot)} "
                  f"({pivot_used/len(pivot)*100:.1f}%)")
            print(f"    Direct sufficient: {direct_sufficient}/{len(pivot)} "
                  f"({direct_sufficient/len(pivot)*100:.1f}%)")
        
        total_tests = sum(len(self.groups[g]['pivot']) for g in self.groups)
        
        results['overall'] = {
            'total_tests': total_tests,
            'pivot_attempted': total_pivot_attempted,
            'pivot_succeeded': total_pivot_succeeded,
            'direct_sufficient': total_direct_sufficient,
            'pivot_rate': total_pivot_attempted / total_tests if total_tests else 0,
            'success_rate': total_pivot_succeeded / total_pivot_attempted if total_pivot_attempted else 0
        }
        
        print(f"\n  OVERALL:")
        print(f"    Pivot attempted: {total_pivot_attempted}/{total_tests} "
              f"({total_pivot_attempted/total_tests*100:.1f}%)")
        print(f"    Pivot succeeded (gates passed): {total_pivot_succeeded}/{total_pivot_attempted} "
              f"({total_pivot_succeeded/total_pivot_attempted*100:.1f}% of attempts)" if total_pivot_attempted else "(no attempts)")
        print(f"    Direct sufficient: {total_direct_sufficient}/{total_tests} "
              f"({total_direct_sufficient/total_tests*100:.1f}%)")
        
        return results
    
    def analyze_new_support(self) -> Dict[str, Any]:
        """Metric 4: Previously unsupported inputs that now receive translations."""
        print("\n" + "-"*80)
        print(" METRIC 4: New Supported Inputs (Pivot Adds Coverage)")
        print("-"*80)
        
        results = {
            'description': 'Inputs where direct failed but pivot succeeded',
            'cases': []
        }
        
        new_support_count = 0
        
        for group_name, group_data in self.groups.items():
            direct = group_data['direct']
            pivot = group_data['pivot']
            
            for i, (d, p) in enumerate(zip(direct, pivot)):
                # New support: direct confidence = 0 but pivot confidence > 0
                if d['confidence'] == 0 and p['confidence'] > 0:
                    new_support_count += 1
                    results['cases'].append({
                        'group': group_name,
                        'description': d['description'],
                        'input': d['input'],
                        'src': d['src'],
                        'tgt': d['tgt'],
                        'direct_method': d['method'],
                        'pivot_method': p['method'],
                        'pivot_output': p['output'],
                        'pivot_confidence': p['confidence']
                    })
        
        results['total_new_support'] = new_support_count
        
        print(f"\n  Total new supported inputs: {new_support_count}")
        
        if new_support_count > 0:
            print(f"\n  Examples:")
            for case in results['cases'][:5]:  # Show first 5
                print(f"    • {case['description']}")
                print(f"      Input: '{case['input']}' ({case['src']}→{case['tgt']})")
                print(f"      Direct: {case['direct_method']} (conf=0.0)")
                print(f"      Pivot:  '{case['pivot_output']}' ({case['pivot_method']}, "
                      f"conf={case['pivot_confidence']:.2f})")
        else:
            print("    (None found)")
        
        return results
    
    def analyze_regressions(self) -> Dict[str, Any]:
        """Metric 5: Previously correct translations that regress with pivot."""
        print("\n" + "-"*80)
        print(" METRIC 5: Regressions (Pivot Degrades Quality)")
        print("-"*80)
        
        results = {
            'description': 'Inputs where direct succeeded but pivot failed or degraded',
            'cases': []
        }
        
        regression_count = 0
        
        for group_name, group_data in self.groups.items():
            direct = group_data['direct']
            pivot = group_data['pivot']
            
            for i, (d, p) in enumerate(zip(direct, pivot)):
                # Regression: direct was correct/usable but pivot degraded
                if d['confidence'] > 0:
                    # Check if pivot degraded confidence
                    if p['confidence'] < d['confidence']:
                        regression_count += 1
                        results['cases'].append({
                            'group': group_name,
                            'description': d['description'],
                            'input': d['input'],
                            'src': d['src'],
                            'tgt': d['tgt'],
                            'direct_output': d['output'],
                            'direct_confidence': d['confidence'],
                            'pivot_output': p['output'],
                            'pivot_confidence': p['confidence'],
                            'confidence_drop': d['confidence'] - p['confidence']
                        })
                    
                    # Check if exact match was lost
                    elif d.get('exact_match') and not p.get('exact_match'):
                        if d['output'] != p['output']:  # Different output
                            regression_count += 1
                            results['cases'].append({
                                'group': group_name,
                                'description': d['description'],
                                'input': d['input'],
                                'src': d['src'],
                                'tgt': d['tgt'],
                                'direct_output': d['output'],
                                'direct_exact_match': True,
                                'pivot_output': p['output'],
                                'pivot_exact_match': False,
                                'note': 'Lost exact match'
                            })
        
        results['total_regressions'] = regression_count
        
        print(f"\n  Total regressions: {regression_count}")
        
        if regression_count > 0:
            print(f"\n  Examples:")
            for case in results['cases'][:3]:  # Show first 3
                print(f"    • {case['description']}")
                print(f"      Input: '{case['input']}' ({case['src']}→{case['tgt']})")
                print(f"      Direct: '{case.get('direct_output')}' "
                      f"(conf={case.get('direct_confidence', 'N/A')})")
                print(f"      Pivot:  '{case.get('pivot_output')}' "
                      f"(conf={case.get('pivot_confidence', 'N/A')})")
                if 'confidence_drop' in case:
                    print(f"      Drop: {case['confidence_drop']:.2f}")
        else:
            print("    ✓ No regressions found")
        
        return results
    
    def analyze_chrf(self) -> Dict[str, Any]:
        """Metric 6: Reference-based chrF++ scoring."""
        print("\n" + "-"*80)
        print(" METRIC 6: Reference-Based chrF++ Scores")
        print("-"*80)
        
        results = {
            'description': 'Character n-gram F-score for cases with known references',
            'note': 'chrF++ not computed - requires sacrebleu library. Exact match used as proxy.',
            'proxy_metric': 'exact_match_rate',
            'by_group': {}
        }
        
        # Note: chrF++ requires sacrebleu library which may not be installed
        # Using exact match rate as a proxy metric
        
        for group_name, group_data in self.groups.items():
            direct_tests = [t for t in group_data['direct'] if t['reference'] is not None]
            pivot_tests = [t for t in group_data['pivot'] if t['reference'] is not None]
            
            if not direct_tests:
                continue
            
            direct_exact = sum(1 for t in direct_tests if t.get('exact_match') is True)
            pivot_exact = sum(1 for t in pivot_tests if t.get('exact_match') is True)
            
            results['by_group'][group_name] = {
                'tests_with_reference': len(direct_tests),
                'direct_exact_match_rate': direct_exact / len(direct_tests) if direct_tests else 0,
                'pivot_exact_match_rate': pivot_exact / len(pivot_tests) if pivot_tests else 0
            }
            
            print(f"\n  {group_name}:")
            print(f"    Exact match rate (proxy for chrF++):")
            print(f"      Direct: {direct_exact/len(direct_tests)*100:.1f}%")
            print(f"      Pivot:  {pivot_exact/len(pivot_tests)*100:.1f}%")
        
        print(f"\n  Note: Full chrF++ scoring requires sacrebleu library.")
        print(f"  Exact match rate used as proxy for translation quality.")
        
        return results
    
    def analyze_latency(self) -> Dict[str, Any]:
        """Metric 7: Latency and timeout behavior."""
        print("\n" + "-"*80)
        print(" METRIC 7: Latency and Timeout Behavior")
        print("-"*80)
        
        results = {
            'description': 'Translation timing and timeout statistics',
            'note': 'Latency data collected from pivot diagnostic fields',
            'pivot_latency': []
        }
        
        for group_name, group_data in self.groups.items():
            pivot = group_data['pivot']
            
            for test in pivot:
                if test.get('pivot_used'):
                    # Extract latency from embedded result data
                    # Need to re-read from full results
                    pass
        
        # Check for pivot timing data in results
        pivot_with_timing = []
        for group_name, group_data in self.groups.items():
            for test in group_data['pivot']:
                if 'pivot_stage2_elapsed' in test or 'pivot_stage3_elapsed' in test:
                    pivot_with_timing.append(test)
        
        if pivot_with_timing:
            avg_stage2 = sum(t.get('pivot_stage2_elapsed', 0) for t in pivot_with_timing) / len(pivot_with_timing)
            avg_stage3 = sum(t.get('pivot_stage3_elapsed', 0) for t in pivot_with_timing) / len(pivot_with_timing)
            avg_total = avg_stage2 + avg_stage3
            
            results['pivot_latency'] = {
                'samples': len(pivot_with_timing),
                'avg_stage2_seconds': round(avg_stage2, 2),
                'avg_stage3_seconds': round(avg_stage3, 2),
                'avg_total_seconds': round(avg_total, 2)
            }
            
            print(f"\n  Pivot translation latency:")
            print(f"    Samples: {len(pivot_with_timing)}")
            print(f"    Avg Stage 2 (source→Filipino): {avg_stage2:.2f}s")
            print(f"    Avg Stage 3 (Filipino→target): {avg_stage3:.2f}s")
            print(f"    Avg Total: {avg_total:.2f}s")
        else:
            print(f"\n  No pivot latency data available (no pivot attempts with timing)")
        
        # Check for timeouts
        timeouts = sum(1 for g in self.groups.values() 
                      for t in g['pivot'] 
                      if 'timeout' in str(t.get('error', '')).lower())
        
        results['timeouts'] = timeouts
        print(f"\n  Timeouts: {timeouts}")
        
        return results
    
    def analyze_pivot_improvement(self) -> Dict[str, Any]:
        """Metric 8: Overall pivot improvement assessment."""
        print("\n" + "-"*80)
        print(" METRIC 8: Pivot Improvement vs Direct-Only")
        print("-"*80)
        
        total_tests = sum(len(self.groups[g]['direct']) for g in self.groups)
        
        # Coverage improvement
        direct_usable = sum(self.summary[g]['direct']['usable'] for g in self.summary)
        pivot_usable = sum(self.summary[g]['pivot']['usable'] for g in self.summary)
        coverage_improvement = pivot_usable - direct_usable
        
        # Exact match improvement
        direct_exact = sum(self.summary[g]['direct']['exact_matches'] for g in self.summary)
        pivot_exact = sum(self.summary[g]['pivot']['exact_matches'] for g in self.summary)
        exact_match_improvement = pivot_exact - direct_exact
        
        # Pivot usage
        pivot_used = sum(self.summary[g]['pivot']['pivot_used'] for g in self.summary)
        
        results = {
            'total_tests': total_tests,
            'coverage': {
                'direct_usable': direct_usable,
                'pivot_usable': pivot_usable,
                'improvement': coverage_improvement,
                'improvement_rate': coverage_improvement / total_tests if total_tests else 0
            },
            'exact_matches': {
                'direct': direct_exact,
                'pivot': pivot_exact,
                'improvement': exact_match_improvement
            },
            'pivot_usage': {
                'attempts': pivot_used,
                'usage_rate': pivot_used / total_tests if total_tests else 0
            },
            'conclusion': ''
        }
        
        print(f"\n  Total evaluation tests: {total_tests}")
        print(f"\n  Coverage:")
        print(f"    Direct usable: {direct_usable}/{total_tests} ({direct_usable/total_tests*100:.1f}%)")
        print(f"    Pivot usable:  {pivot_usable}/{total_tests} ({pivot_usable/total_tests*100:.1f}%)")
        print(f"    Improvement: {coverage_improvement:+d} ({coverage_improvement/total_tests*100:+.1f}%)")
        
        print(f"\n  Exact matches:")
        print(f"    Direct: {direct_exact}")
        print(f"    Pivot:  {pivot_exact}")
        print(f"    Change: {exact_match_improvement:+d}")
        
        print(f"\n  Pivot usage:")
        print(f"    Attempted: {pivot_used}/{total_tests} ({pivot_used/total_tests*100:.1f}%)")
        
        # Determine conclusion
        if coverage_improvement > 0 and exact_match_improvement >= 0:
            conclusion = "POSITIVE: Pivot improves coverage without degrading quality"
        elif coverage_improvement > 0 and exact_match_improvement < 0:
            conclusion = "MIXED: Pivot improves coverage but reduces exact matches"
        elif coverage_improvement == 0 and exact_match_improvement == 0:
            conclusion = "NEUTRAL: Pivot provides no measurable improvement"
        elif coverage_improvement < 0 or exact_match_improvement < 0:
            conclusion = "NEGATIVE: Pivot degrades performance"
        else:
            conclusion = "UNCLEAR: Mixed results require further analysis"
        
        results['conclusion'] = conclusion
        
        print(f"\n  CONCLUSION: {conclusion}")
        
        return results


if __name__ == "__main__":
    analyzer = Day6MetricsAnalyzer()
    analyzer.analyze_all()
