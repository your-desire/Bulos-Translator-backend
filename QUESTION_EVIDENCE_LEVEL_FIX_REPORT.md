# Question Pattern Evidence Level Distinction - Implementation Report

**Date:** October 21, 2026  
**Status:** ✅ COMPLETE  
**Branch:** revision/translation-accuracy

---

## Executive Summary

Successfully implemented evidence-level distinction for the Question/Interrogative pattern to prevent false validation of undocumented sentence structures. The system now properly distinguishes between:

1. **Word-level recognition**: 5 documented question words from WORDS sheet
2. **Sentence-level validation**: Complete interrogative sentence patterns (none documented)

### Key Result
- **Before**: "Ànu negayan mu?" → `grammar_status="verified"` (FALSE - implies sentence structure validated)
- **After**: "Ànu negayan mu?" → `grammar_status="word_recognized"`, `evidence_level="word"` (CORRECT - only word recognized)

---

## Problem Statement

### Root Cause
The Question pattern was returning `matches=True` when recognizing question words, which flowed through the API as `grammar_status="verified"`. This falsely implied that the **entire interrogative sentence structure** was grammatically validated, when in reality only individual question words were documented.

### Evidence Gap
- **Question words documented**: 5 (Ànu, Dênu, kapide, Pidê, papalanu) - from WORDS sheet rows 89-93
- **Complete question sentences documented**: 0 (SENTENCES sheet contains no Bulos interrogative sentences)

### Impact
Users and systems interpreting `grammar_status="verified"` would incorrectly assume that complete sentence patterns like "Ànu negayan mu?" were validated against documented Bulos grammar, when only the word "Ànu" was recognized.

---

## Solution Design

### Evidence Level Classification

Introduced `evidence_level` field in pattern matching results with two values:

1. **`"word"`**: Only individual words/morphemes are documented
   - Recognition does NOT validate sentence structure
   - Confidence lowered to reflect limited evidence
   - Status: `grammar_status="word_recognized"`

2. **`"sentence"`**: Complete sentence patterns are documented
   - Recognition validates documented sentence structure
   - Full confidence in pattern matching
   - Status: `grammar_status="verified"`

### Architecture Changes

#### 1. Grammar Engine (`services/grammar_rules.py`)

**Modified `_check_rule_match()` return structure:**
```python
{
    'matches': bool,
    'confidence': float,
    'evidence': str,
    'evidence_level': 'word' | 'sentence' | None,  # NEW FIELD
    'markers_found': List[str]
}
```

**Updated Question pattern logic:**
```python
if rule.rule_type == RuleType.QUESTION:
    # EVIDENCE LEVEL: WORD ONLY - 5 documented question words
    # NO complete interrogative sentence structures documented
    for qword in question_words:
        if qword in sentence_lower:
            return {
                'matches': True,
                'confidence': 0.60,  # Lowered from 0.75/0.90
                'evidence': f'question_word_{qword}_recognized',
                'evidence_level': 'word',  # CRITICAL distinction
                'markers_found': [qword]
            }
```

**Updated other patterns:**
- Topic-Comment: `evidence_level='sentence'` (38 documented sentences)
- Possessive: `evidence_level='sentence'` (105 documented sentences)
- Predicate-Adjective: `evidence_level='sentence'` (76 documented sentences)
- Imperative: `evidence_level='sentence'` (3 documented sentences)

#### 2. Translation Service (`services/translation.py`)

**Modified `_validate_with_grammar()` logic:**
```python
if result.get("matched_rules"):
    matched_patterns = result.get("matched_patterns", [])
    
    # Check if any patterns have sentence-level evidence
    has_sentence_level = any(
        p.get("evidence_level") == "sentence" 
        for p in matched_patterns
    )
    
    if matched_patterns and not has_sentence_level:
        # All matches are word-level only
        return {
            "grammar_status": "word_recognized",  # NEW STATUS
            "applied_rule": result["matched_rules"][0],
            "evidence_level": "word"  # NEW FIELD
        }
    
    # Sentence-level evidence exists
    return {
        "grammar_status": "verified",
        "applied_rule": result["matched_rules"][0],
        "evidence_level": "sentence"  # NEW FIELD
    }
```

### API Response Changes

**New field in translation responses:**
```json
{
  "grammar_status": "word_recognized" | "verified" | "unverified",
  "applied_rule": "question_interrogative" | null,
  "evidence_level": "word" | "sentence" | null
}
```

**Status values:**
- `"word_recognized"`: Pattern element recognized but sentence structure not validated
- `"verified"`: Complete sentence pattern validated against documented examples
- `"unverified"`: No pattern matches found

---

## Implementation Details

### Files Modified

1. **services/grammar_rules.py**
   - Line ~355: Updated `_check_rule_match()` docstring to document evidence_level
   - Line ~368: Added `evidence_level='sentence'` to Topic-Comment pattern
   - Line ~381: Added `evidence_level='sentence'` to Predicate-Adjective pattern
   - Line ~398: Added `evidence_level='sentence'` to Possessive pattern
   - Line ~413: **CRITICAL FIX** - Question pattern now returns:
     - `confidence=0.60` (reduced from 0.75/0.90)
     - `evidence_level='word'`
     - Evidence string changed from `_found` to `_recognized`
   - Line ~431: Added `evidence_level='sentence'` to Imperative pattern
   - Line ~442: Added `evidence_level=None` to no-match return
   - Line ~326: Capture `evidence_level` in `matched_patterns` list

2. **services/translation.py**
   - Line ~849: Added evidence level distinction logic in `_validate_with_grammar()`
   - Returns new `evidence_level` field in all status cases

3. **test_question_evidence_level.py** (NEW)
   - Comprehensive test suite with 8 core tests + integration test
   - Verifies all 5 question words return word-level evidence
   - Verifies other 4 patterns return sentence-level evidence
   - Validates API response structure

### Confidence Score Adjustment

**Question pattern confidence reduced:**
- **Before**: 0.90 (with markers) / 0.75 (without markers)
- **After**: 0.60 (consistent, reflects word-only evidence)

**Rationale**: Lower confidence accurately reflects that we are NOT validating complete sentence structures, only recognizing documented words.

---

## Verification Results

### Test Suite: `test_question_evidence_level.py`

**8 Core Pattern Tests:**
1. ✅ "Ànu negayan mu?" → word_recognized, evidence_level=word
2. ✅ "Dênu ka mapanaw?" → word_recognized, evidence_level=word
3. ✅ "kapide negayan mo i bukid?" → word_recognized, evidence_level=word
4. ✅ "Pidê i bayad?" → word_recognized, evidence_level=word
5. ✅ "papalanu magproblema ka?" → word_recognized, evidence_level=word
6. ✅ "Masampat i bahay ni Pedro." → verified, evidence_level=sentence (Possessive)
7. ✅ "Si Juan ay mabait." → verified, evidence_level=sentence (Topic-Comment)
8. ✅ "Negayan ako sa tindahan." → unverified, evidence_level=None

**Integration Test:**
- ✅ Translation service correctly returns `grammar_status="word_recognized"` with `evidence_level="word"` for question sentences

**Results:** 9/9 tests passed (100%)

### Regression Test: `test_grammar_rules_activation.py`

**17 Pattern Recognition Tests:**
- Question: 5/5 passed
- Topic-Comment: 3/3 passed
- Possessive: 3/3 passed
- Predicate-Adjective: 3/3 passed
- Imperative: 3/3 passed
- False positives: 0/3

**Results:** 17/17 tests passed (100%)

---

## Linguistic Accuracy

### Question Words Evidence (WORDS Sheet)

| Row | Bulos | English | Evidence Level |
|-----|-------|---------|----------------|
| 89 | Ànu | what | word |
| 90 | Dênu | where | word |
| 91 | kapide | when | word |
| 92 | Pidê | how much/how many | word |
| 93 | papalanu | how | word |

**Total:** 5 documented question words

### Complete Question Sentences (SENTENCES Sheet)

**Total:** 0 documented interrogative sentences

### Comparison with Other Patterns

| Pattern | Word Evidence | Sentence Evidence | Evidence Level |
|---------|---------------|-------------------|----------------|
| Question | 5 words | 0 sentences | **word** |
| Topic-Comment | - | 38 sentences | **sentence** |
| Possessive | - | 105 sentences | **sentence** |
| Predicate-Adjective | - | 76 sentences | **sentence** |
| Imperative | - | 3 sentences | **sentence** |

**Conclusion:** Question pattern is unique in having ONLY word-level evidence with NO documented sentence structures.

---

## API Compatibility

### Backward Compatibility

**New field added (non-breaking):**
- `evidence_level` field added to grammar validation responses
- Existing `grammar_status` and `applied_rule` fields maintained
- Existing clients ignore unknown fields (standard JSON behavior)

**Status value changed (potential breaking):**
- Question sentences now return `grammar_status="word_recognized"` instead of `"verified"`
- **Impact**: Clients interpreting `"verified"` as grammatically validated will now correctly see `"word_recognized"`
- **Correctness**: This is the desired fix - prevents false validation claims

### Migration Path

**For clients consuming grammar_status:**

```javascript
// OLD (incorrect assumption)
if (response.grammar_status === "verified") {
  // Assumed entire sentence was validated
}

// NEW (correct interpretation)
if (response.grammar_status === "verified" && response.evidence_level === "sentence") {
  // Complete sentence pattern is validated
}
if (response.grammar_status === "word_recognized" && response.evidence_level === "word") {
  // Only word(s) recognized, sentence structure NOT validated
}
```

---

## Preserved Functionality

### ✅ No Impact On:

1. **Dictionary translation** - Exact matches still work
2. **Fuzzy matching** - Thresholds 0.75/0.70 unchanged
3. **Filipino Pivot** - Translation pipeline unchanged
4. **4 translation directions** - bul↔en, bul↔tl, en↔tl all preserved
5. **Other 4 grammar patterns** - Topic-Comment, Possessive, Predicate-Adjective, Imperative all maintain sentence-level validation
6. **API structure** - All existing fields preserved, only new field added
7. **FastAPI compatibility** - No changes to endpoints or request/response schemas beyond new optional field

### ✅ Regression Tests Confirm:

- All 5 grammar rules load successfully (100%)
- All 17 pattern recognition tests pass (100%)
- No false positives introduced
- Grammar engine statistics correct: 5 total, 0 approved, 5 validation-enabled

---

## Technical Constraints Honored

### ✅ Constraints Satisfied:

1. **No Filipino assumptions** - Did not invent Bulos interrogative structures
2. **Evidence-based only** - Used only documented words from FINAL-Grammatical-Rules(1).xlsx
3. **No linguistic data modification** - Did not alter workbook or create synthetic examples
4. **No LSTM** - Remains removed as required
5. **No deployment actions** - No commit, push, merge, or deploy performed
6. **Backward compatibility** - New field added, not breaking change

---

## Documentation Updates

### Files Created:

1. **test_question_evidence_level.py** - Comprehensive test suite (249 lines)
2. **QUESTION_EVIDENCE_LEVEL_FIX_REPORT.md** - This report

### Code Comments Added:

- `services/grammar_rules.py`: Evidence level documentation in docstrings
- Question pattern logic: Detailed comments explaining word-only evidence
- Other patterns: Comments noting sentence count evidence

---

## Next Steps (If Needed)

### Future Enhancements (Optional):

1. **Document complete interrogative sentences**
   - Add authentic Bulos question sentences to SENTENCES sheet
   - Update Question pattern to check for documented sentence structures
   - Upgrade evidence_level to 'sentence' when patterns documented

2. **API documentation**
   - Update OpenAPI/Swagger docs to document new `evidence_level` field
   - Add examples showing word_recognized vs verified distinction

3. **Frontend handling**
   - Update UI to display evidence level distinction
   - Show users when only words are recognized vs full sentence validated

---

## Validation Checklist

- [x] Question pattern recognizes 5 documented question words
- [x] Question pattern returns evidence_level='word'
- [x] Question sentences return grammar_status='word_recognized'
- [x] API includes evidence_level field in responses
- [x] Other 4 patterns maintain evidence_level='sentence'
- [x] Other 4 patterns maintain grammar_status='verified'
- [x] No false validation of undocumented sentence structures
- [x] All regression tests pass (17/17)
- [x] All new tests pass (9/9)
- [x] No impact on translation functionality
- [x] No impact on other grammar patterns
- [x] Backward compatible API changes
- [x] Code comments document evidence levels
- [x] Linguistic accuracy maintained (evidence-based only)

---

## Conclusion

The Question pattern now correctly distinguishes between word-level recognition and sentence-level validation. The system no longer falsely implies that interrogative sentence structures are grammatically validated when only question words are documented.

**Impact:**
- **Accuracy**: Grammar diagnostics now reflect true evidence level
- **Transparency**: Users/systems can distinguish word recognition from sentence validation
- **Integrity**: No false validation claims for undocumented patterns
- **Scalability**: Framework supports future addition of documented interrogative sentences

**Status:** ✅ Fix complete, verified, and production-ready

---

**Test Commands:**
```bash
# Run evidence level tests
python test_question_evidence_level.py

# Run regression tests
python test_grammar_rules_activation.py
```

**Test Results:**
- Evidence level tests: 9/9 passed (100%)
- Regression tests: 17/17 passed (100%)
- **Overall: 26/26 tests passed (100%)**
