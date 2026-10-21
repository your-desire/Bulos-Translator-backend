# GitHub Backup Commit File Manifest

**Date:** October 21, 2026  
**Branch:** backup/final-grammar-aware-pivot  
**Repository:** https://github.com/your-desire/Bulos-Backend-Backup

---

## FILES TO INCLUDE

### Core Backend Files (Modified - INCLUDE)

✅ **config.py**
- Grammar feature flags
- Pivot control settings
- Production-safe defaults
- No secrets

✅ **services/grammar_rules.py**
- Grammar engine implementation
- Evidence level distinction logic
- Pattern matching for 5 grammar rules
- No sensitive data

✅ **services/translation.py**
- Translation service with Filipino Pivot
- Grammar validation integration
- Evidence-level checking
- No API keys

✅ **utils/fuzzy_match.py**
- Fuzzy matching thresholds (0.75/0.70)
- False positive safeguards
- No sensitive data

✅ **data/pos_annotations.json**
- POS annotations from FINAL-Grammatical-Rules(1).xlsx
- 506 words, 159 patterns
- Publicly shareable linguistic data

✅ **extract_pos_annotations.py** (DELETED)
- Removed from repository (marked as deleted)
- Will be excluded from backup

### Essential Grammar Dataset Files (NEW - INCLUDE)

✅ **data/FINAL-Grammatical-Rules.xlsx**
- Primary grammar evidence source
- SENTENCES, WORDS, COMMON WORDS, LETTERS sheets
- Authorized for public sharing
- **Verification:** Contains authentic Bulos linguistic data

✅ **data/grammar_rules.yaml**
- 5 grammar rule definitions
- Extracted from FINAL-Grammatical-Rules.xlsx
- Validation-enabled, generation-disabled
- Publicly shareable

### Test Files (NEW - INCLUDE)

✅ **test_question_evidence_level.py**
- Evidence level distinction tests
- 9 test cases
- Documentation value

✅ **test_grammar_rules_activation.py**
- Grammar activation tests
- 17 test cases
- Regression testing

✅ **verify_question_fix.py**
- Interactive verification demo
- Educational value

### Documentation Files (NEW - INCLUDE - SELECT)

✅ **QUESTION_EVIDENCE_LEVEL_FIX_REPORT.md**
- Technical implementation documentation
- Evidence level fix details
- High value

✅ **QUESTION_EVIDENCE_FIX_SUMMARY.md**
- Quick reference guide
- User-facing documentation

✅ **FINAL_BACKEND_VERIFICATION.md**
- Comprehensive verification report
- API examples
- Production readiness

✅ **GITHUB_BACKUP_VERIFICATION.md**
- Test results summary
- Component verification
- Backup checklist

✅ **FILIPINO_PIVOT_VERIFICATION_REPORT.md**
- Pivot implementation details
- Test results
- Feature documentation

✅ **GRAMMAR_RULES_ACTIVATION_COMPLETE_REPORT.md**
- Grammar activation documentation
- Implementation details

✅ **README.md** (if exists)
- Project overview
- Setup instructions

---

## FILES TO EXCLUDE

### ❌ Environment Files (EXCLUDED BY .gitignore)
- `.env` - Contains secrets and API keys
- `.envrc` - Environment variables
- `.venv/` - Virtual environment

### ❌ Temporary/Generated Files (DO NOT COMMIT)
- `*.pyc` - Bytecode
- `__pycache__/` - Cached Python
- `*.log` - Log files
- `.pytest_cache/` - Test cache

### ❌ Development/Analysis Scripts (NOT NEEDED FOR BACKUP)
- `analyze_*.py` - Analysis scripts (72 files)
- `check_*.py` - Debug scripts
- `debug_*.py` - Debug scripts
- `diagnose_*.py` - Diagnostic scripts
- `evaluate_*.py` - Evaluation scripts
- `find_*.py` - Search scripts
- `inspect_*.py` - Inspection scripts
- `investigate_*.py` - Investigation scripts
- `quick_*.py` - Quick test scripts
- `test_*.py` (except the 3 selected above)
- `verify_*.py` (except verify_question_fix.py)
- `compare_*.py` - Comparison scripts
- `prepare_*.py` - Preparation scripts
- `extract_*.py` - Extraction scripts
- `pandas_*.py` - Data analysis

### ❌ Obsolete LSTM Files (ARCHIVED - DO NOT COMMIT)
- `backups/lstm_models_archived/`
- `backups/lstm_results_archived/`
- `backups/lstm_tests_archived/`
- `backups/lstm_training_archived/`
- `data/lstm_training/`
- `data/lstm_full_training/`

### ❌ Excessive Documentation (EXCLUDE - TOO MANY)
Most of the 60+ markdown documentation files in root:
- `ACTUAL_FINDINGS_REPORT.md`
- `ANDROID_FASTAPI_INTEGRATION_ANALYSIS.md`
- `BACKEND_RECOVERY_COMPARISON_REPORT.md`
- `BACKUP_COMPLETE_SUMMARY.md`
- (58+ more similar files)

**Reason:** These are development/analysis artifacts, not core documentation

**Keep Only:** The 7 selected documentation files listed above

### ❌ Superseded Grammar Annotations (DO NOT COMMIT)
- `data/grammar_archive_old/` - Old grammar data
- `data/pos_annotations_from_final_workbook.json` - Superseded by data/pos_annotations.json
- `generated_grammar_annotations.json` - If exists

### ❌ Backup/Patch Files (DO NOT COMMIT)
- `backup_comparison/`
- `bulos-backend-copy.git/`
- `workspace_diff_*.patch`
- `workspace_snapshot_*.txt`
- `workspace_staged_*.patch`

### ❌ Experimental Files (DO NOT COMMIT)
- `experiments/`
- `experiment_output.txt`
- `Untitled0.ipynb`
- `colab_train_lstm_models.ipynb`

### ❌ JSON/Text Output Files (DO NOT COMMIT)
- `*.json` (except grammar_rules and essential configs)
- `*_output.txt`
- `*_results.txt`
- `benchmark_results.json`
- `corpus_analysis_output.txt`
- `grammar_patterns_output.txt`
- `translation_failures_output.txt`

### ❌ MongoDB Export Files (DO NOT COMMIT)
- `mongodb_additional_words.*` (csv, json, md)

### ❌ Scripts Directory (SELECT CAREFULLY)
Include only if essential:
- Most `scripts/*.py` files are development/analysis tools
- Exclude unless required for production

---

## VERIFICATION CHECKLIST

### ✅ Security Verification

- [x] `.env` file excluded via .gitignore
- [x] No API keys in committed files
- [x] No credentials in config files
- [x] No personal information
- [x] Git history checked (no secrets found in recent commits)

### ✅ Linguistic Data Authorization

- [x] FINAL-Grammatical-Rules.xlsx authorized for public sharing
- [x] grammar_rules.yaml derived from authorized source
- [x] pos_annotations.json contains publicly shareable data
- [x] No proprietary linguistic data included

### ✅ LSTM Removal Confirmation

- [x] No LSTM model files in commit
- [x] LSTM archived in backups/ (excluded from commit)
- [x] No LSTM references in active code

### ✅ Code Quality

- [x] All tests passing (26/26)
- [x] No temporary debug code
- [x] Production-safe defaults
- [x] Grammar generation disabled

---

## COMMIT STRATEGY

### Stage Only Essential Files

```bash
# Core backend changes
git add config.py
git add services/grammar_rules.py
git add services/translation.py
git add utils/fuzzy_match.py
git add data/pos_annotations.json
git add extract_pos_annotations.py  # Deletion

# Essential grammar datasets
git add data/FINAL-Grammatical-Rules.xlsx
git add data/grammar_rules.yaml

# Key test files
git add test_question_evidence_level.py
git add test_grammar_rules_activation.py
git add verify_question_fix.py

# Core documentation (7 files)
git add QUESTION_EVIDENCE_LEVEL_FIX_REPORT.md
git add QUESTION_EVIDENCE_FIX_SUMMARY.md
git add FINAL_BACKEND_VERIFICATION.md
git add GITHUB_BACKUP_VERIFICATION.md
git add FILIPINO_PIVOT_VERIFICATION_REPORT.md
git add GRAMMAR_RULES_ACTIVATION_COMPLETE_REPORT.md
git add COMMIT_FILE_MANIFEST.md  # This file
```

### Total Files to Commit: ~19 files

- Modified core files: 6
- New grammar datasets: 2
- Test files: 3
- Documentation: 7
- Manifest: 1

---

## EXCLUSION SUMMARY

**Excluded File Categories:**
1. Environment files (.env)
2. Temporary/cache files
3. 150+ development/analysis scripts
4. 60+ excessive markdown reports
5. Obsolete LSTM artifacts
6. Backup/patch files
7. Experimental notebooks
8. JSON output files
9. MongoDB exports

**Total Untracked Files:** ~170
**Files to Commit:** ~19
**Exclusion Rate:** ~89%

---

## PUBLIC SHARING SAFETY

✅ **Safe for Public Repository:**
- All committed code is production-ready
- No secrets or credentials
- Linguistic data authorized for sharing
- No proprietary information
- No personal data

---

**Manifest Complete - Ready for Staging**
