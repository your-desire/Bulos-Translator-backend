"""Test that grammar rules and POS annotations load correctly."""

import asyncio
from services.translation import TranslationService


async def test():
    print("=" * 70)
    print("GRAMMAR RULES AND POS ANNOTATIONS LOADING TEST")
    print("=" * 70)
    
    service = TranslationService()
    await service.initialize()
    
    print("\n[1/2] Testing Grammar Rules Loading...")
    assert service.grammar_engine is not None, "Grammar engine should be initialized"
    
    stats = service.grammar_engine.get_statistics()
    print(f"   ✓ Grammar engine loaded")
    print(f"   • Total rules: {stats['total_rules']}")
    print(f"   • Approved rules: {stats['approved_rules']}")
    print(f"   • Validation-enabled: {stats['validation_enabled']}")
    
    if stats['total_rules'] > 0:
        print(f"\n   Rules by status:")
        for status, count in stats['rules_by_status'].items():
            if count > 0:
                print(f"   • {status}: {count}")
        
        print(f"\n   Rules by type:")
        for rtype, count in stats['rules_by_type'].items():
            if count > 0:
                print(f"   • {rtype}: {count}")
    
    print("\n[2/2] Testing POS Annotations Loading...")
    assert service.pos_annotations is not None, "POS annotations should be loaded"
    
    meta = service.pos_annotations.get('metadata', {})
    print(f"   ✓ POS annotations loaded")
    print(f"   • Total words: {meta.get('total_words', 0)}")
    print(f"   • Total sentences: {meta.get('total_sentences', 0)}")
    print(f"   • Total patterns: {meta.get('total_patterns', 0)}")
    
    if 'statistics' in service.pos_annotations:
        pos_stats = service.pos_annotations['statistics']
        
        print(f"\n   POS distribution:")
        for pos, count in pos_stats.get('pos_distribution', {}).items():
            if count > 0:
                print(f"   • {pos}: {count}")
        
        print(f"\n   Evidence levels:")
        for level, count in pos_stats.get('evidence_levels', {}).items():
            if count > 0:
                print(f"   • {level}: {count}")
    
    print("\n" + "=" * 70)
    print("✅ ALL LOADING TESTS PASSED")
    print("=" * 70)
    
    print("\n📋 SUMMARY:")
    print(f"   • Grammar rules loaded: {stats['total_rules']} rules")
    print(f"   • POS annotations loaded: {meta.get('total_words', 0)} words")
    print(f"   • Validation-enabled rules: {stats['validation_enabled']}")
    print(f"   • API will now return grammar_status based on loaded rules")
    

if __name__ == "__main__":
    asyncio.run(test())
