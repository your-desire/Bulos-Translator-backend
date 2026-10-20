"""
Translation service.

Routing:
  en Γåö tl  ΓåÆ  Google Translate (primary)
               CTranslate2 OPUS-MT (fallback when Google is blocked)
  bul Γåö en / bul Γåö tl  ΓåÆ  4-step internal pipeline:
      Step 1 ΓÇö Phrase matching   : exact full-text lookup in phrase_index
      Step 2 ΓÇö Word matching     : greedy longest-match token-by-token
      Step 3 ΓÇö Fuzzy matching    : Levenshtein, threshold 0.75
      Step 4 ΓÇö Lenient fuzzy     : Levenshtein, threshold 0.50 (bul pairs only)
                                   (OPUS-MT has no Bulos support)

For en Γåö tl pairs the pipeline is also run as a fallback so that even if
Google AND OPUS-MT are both unavailable there is still a best-effort result.
"""

import asyncio
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import settings
from utils.fuzzy_match import levenshtein_similarity
from utils.logging_config import get_logger
from services.grammar_rules import get_grammar_engine, GrammarRulesEngine

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# OPUS-MT singleton ΓÇö loaded lazily on first use
# ---------------------------------------------------------------------------

_opus_translator = None


def _get_opus():
    """Return the singleton OpusTranslator, loading it once on first call."""
    global _opus_translator
    if _opus_translator is None:
        try:
            from services.opus_translator import get_opus_translator
            _opus_translator = get_opus_translator()
        except Exception as e:
            logger.warning(f"OPUS translator unavailable: {e}")
            _opus_translator = False  # sentinel ΓÇö don't retry
    return _opus_translator if _opus_translator is not False else None


# ---------------------------------------------------------------------------
# Fuzzy thresholds
# ---------------------------------------------------------------------------

FUZZY_THRESHOLD         = 0.75  # step 3 ΓÇö strict
FUZZY_THRESHOLD_LENIENT = 0.50  # step 4 bul ΓÇö lenient
FUZZY_MIN_LEN           = 3     # skip tokens shorter than this

# Google Translate language codes
_GOOGLE_LANG = {"en": "en", "tl": "tl"}


class TranslationService:
    """
    Translates text.
    - en Γåö tl  : Google Translate ΓåÆ OPUS-MT fallback ΓåÆ internal pipeline
    - bul Γåö *  : phrase ΓåÆ word ΓåÆ fuzzy(0.75) ΓåÆ lenient fuzzy(0.50)
    """

    SUPPORTED_PAIRS = [
        ("bul", "en"), ("en", "bul"),
        ("bul", "tl"), ("tl", "bul"),
        ("en",  "tl"), ("tl", "en"),
    ]

    def __init__(self):
        self.phrase_index: Dict[str, List[Tuple[str, str, int]]] = {}
        self.timeout = settings.translation_timeout_seconds
        self.grammar_engine: Optional[GrammarRulesEngine] = None
        self.pos_annotations: Optional[Dict] = None
        logger.info(
            f"TranslationService initialised (timeout={self.timeout}s). "
            "enΓåötl ΓåÆ GoogleΓåÆOPUS-MTΓåÆpipeline | bulΓåö* ΓåÆ phraseΓåÆwordΓåÆfuzzyΓåÆlenient-fuzzy"
        )

    # -----------------------------------------------------------------------
    # Startup
    # -----------------------------------------------------------------------

    async def initialize(self) -> None:
        logger.info("Initialising translation service...")
        try:
            dictionary_data = await self._load_dictionary_data()
            alphabet_data   = await self._load_alphabet_data()
            sentence_data   = await self._load_sentence_data()
            all_vocabulary  = dictionary_data + alphabet_data
            self._build_translation_indexes(all_vocabulary, sentence_data)
            
            # Initialize grammar engine and load rules
            await self._load_grammar_rules()
            
            # Load POS annotations
            await self._load_pos_annotations()
            
            logger.info(
                f"Translation service ready ΓÇö "
                f"{len(self.phrase_index)} phrase keys, "
                f"{sum(len(v) for v in self.phrase_index.values())} total entries"
            )
        except Exception as e:
            logger.error(f"Failed to initialise translation service: {e}", exc_info=True)
            raise

    # -----------------------------------------------------------------------
    # Data loading
    # -----------------------------------------------------------------------

    async def _load_dictionary_data(self) -> List[Dict[str, str]]:
        path = Path(__file__).parent.parent / "dictionary.json"
        if not path.exists():
            raise FileNotFoundError(f"dictionary.json not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = []
        for cat in data.get("categories", []):
            for e in cat.get("entries", []):
                bul = e.get("BULOS",    "").strip()
                tl  = e.get("FILIPINO", "").strip()
                en  = e.get("ENGLISH",  "").strip()
                if bul and tl and en and bul != "ΓÇö" and tl != "ΓÇö":
                    entries.append({"bul": bul, "tl": tl, "en": en})
        logger.info(f"Loaded {len(entries)} dictionary entries")
        return entries

    async def _load_alphabet_data(self) -> List[Dict[str, str]]:
        path = Path(__file__).parent.parent / "alphabet.json"
        if not path.exists():
            logger.warning("alphabet.json not found")
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries, seen = [], set()
        for letter in data.get("letters", []):
            for pos in ["initial", "medial", "final"]:
                for e in letter.get("examples", {}).get(pos, []):
                    bul = (e.get("BULOS")    or "").strip()
                    tl  = (e.get("FILIPINO") or "").strip()
                    en  = (e.get("ENGLISH")  or "").strip()
                    key = f"{bul.lower()}|{tl.lower()}|{en.lower()}"
                    if key in seen or not (bul and tl and en) or bul == "ΓÇö" or tl == "ΓÇö":
                        continue
                    entries.append({"bul": bul, "tl": tl, "en": en})
                    seen.add(key)
        logger.info(f"Loaded {len(entries)} alphabet entries")
        return entries

    async def _load_sentence_data(self) -> List[Dict[str, str]]:
        path = Path(__file__).parent.parent / "sentence.json"
        if not path.exists():
            logger.warning("sentence.json not found")
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        entries = []
        for e in data.get("entries", []):
            bul = (e.get("BULOS")    or "").strip()
            tl  = (e.get("FILIPINO") or "").strip()
            en  = (e.get("ENGLISH")  or "").strip()
            if bul and tl and en:
                entries.append({"bul": bul, "tl": tl, "en": en})
        logger.info(f"Loaded {len(entries)} sentence entries")
        return entries

    # -----------------------------------------------------------------------
    # Index building
    # -----------------------------------------------------------------------

    def _normalize_text(self, text: str) -> str:
        norm = unicodedata.normalize("NFD", text)
        norm = "".join(c for c in norm if unicodedata.category(c) != "Mn")
        norm = norm.lower().strip()
        norm = re.sub(r"\s+", " ", norm)
        norm = norm.rstrip(".!?,;:")
        return norm

    def _build_translation_indexes(
        self,
        dictionary_data: List[Dict[str, str]],
        sentence_data:   List[Dict[str, str]],
    ) -> None:
        self.phrase_index = {}

        def _add(key, translation, pair, wc):
            self.phrase_index.setdefault(key, []).append((translation, pair, wc))

        def _add_if_missing(key, translation, pair, wc):
            lst = self.phrase_index.setdefault(key, [])
            if not any(p == pair for _, p, _ in lst):
                lst.append((translation, pair, wc))

        for entry in sentence_data:
            bul, tl, en = entry["bul"], entry["tl"], entry["en"]
            bn, tn, enn = self._normalize_text(bul), self._normalize_text(tl), self._normalize_text(en)
            bw, tw, ew  = len(bn.split()), len(tn.split()), len(enn.split())
            _add(tn,  bul, "tl_to_bul", tw); _add(bn,  tl,  "bul_to_tl", bw)
            _add(enn, bul, "en_to_bul", ew); _add(bn,  en,  "bul_to_en", bw)
            _add(enn, tl,  "en_to_tl",  ew); _add(tn,  en,  "tl_to_en",  tw)

        for entry in dictionary_data:
            bul, tl, en = entry["bul"], entry["tl"], entry["en"]
            bn, tn, enn = self._normalize_text(bul), self._normalize_text(tl), self._normalize_text(en)
            bw, tw, ew  = len(bn.split()), len(tn.split()), len(enn.split())
            _add_if_missing(tn,  bul, "tl_to_bul", tw); _add_if_missing(bn,  tl,  "bul_to_tl", bw)
            _add_if_missing(enn, bul, "en_to_bul", ew); _add_if_missing(bn,  en,  "bul_to_en", bw)
            _add_if_missing(enn, tl,  "en_to_tl",  ew); _add_if_missing(tn,  en,  "tl_to_en",  tw)

        logger.info(f"Built phrase index with {len(self.phrase_index)} unique keys")

    # -----------------------------------------------------------------------
    # Grammar rules and POS annotations loading
    # -----------------------------------------------------------------------

    async def _load_grammar_rules(self) -> None:
        """Load grammar rules from YAML file if available."""
        rules_path = Path(__file__).parent.parent / "data" / "grammar_rules_template.yaml"
        
        if rules_path.exists():
            try:
                from services.grammar_rules import initialize_grammar_engine
                self.grammar_engine = initialize_grammar_engine(rules_path)
                stats = self.grammar_engine.get_statistics()
                logger.info(
                    f"Grammar rules loaded: {stats['total_rules']} total, "
                    f"{stats['approved_rules']} approved, "
                    f"{stats['validation_enabled']} validation-enabled"
                )
            except Exception as e:
                logger.error(f"Failed to load grammar rules: {e}")
                self.grammar_engine = get_grammar_engine()
                logger.warning("Using empty grammar engine")
        else:
            self.grammar_engine = get_grammar_engine()
            logger.info("No grammar rules file found (data/grammar_rules_template.yaml)")

    async def _load_pos_annotations(self) -> None:
        """Load POS annotations from JSON file if available."""
        pos_path = Path(__file__).parent.parent / "data" / "pos_annotations.json"
        
        self.pos_annotations = None
        
        if pos_path.exists():
            try:
                with open(pos_path, 'r', encoding='utf-8') as f:
                    self.pos_annotations = json.load(f)
                
                meta = self.pos_annotations.get('metadata', {})
                logger.info(
                    f"POS annotations loaded: {meta.get('total_words', 0)} words, "
                    f"{meta.get('total_patterns', 0)} patterns"
                )
            except Exception as e:
                logger.error(f"Failed to load POS annotations: {e}")
                self.pos_annotations = None
        else:
            logger.info("No POS annotations file found (data/pos_annotations.json)")

    # -----------------------------------------------------------------------
    # Google Translate helper
    # -----------------------------------------------------------------------

    async def _translate_google(
        self, text: str, src: str, tgt: str
    ) -> Dict[str, Any]:
        gs, gt = _GOOGLE_LANG.get(src, src), _GOOGLE_LANG.get(tgt, tgt)
        try:
            from deep_translator import GoogleTranslator
            loop       = asyncio.get_event_loop()
            translated = await loop.run_in_executor(
                None,
                lambda: GoogleTranslator(source=gs, target=gt).translate(text),
            )
            if translated and translated.strip().lower() != text.strip().lower():
                logger.info(f"[Google] '{text}' ({src}ΓåÆ{tgt}) ΓåÆ '{translated}'")
                return {"translated_text": translated, "confidence": 1.0,
                        "translation_method": "google_translate"}
        except Exception as e:
            logger.warning(f"[Google] Failed ({src}ΓåÆ{tgt}): {e}")
        return {"translated_text": text, "confidence": 0.0,
                "translation_method": "google_failed"}

    # -----------------------------------------------------------------------
    # OPUS-MT helper  (en Γåö tl)
    # -----------------------------------------------------------------------

    async def _translate_opus(
        self, text: str, src: str, tgt: str
    ) -> Dict[str, Any]:
        opus = _get_opus()
        if opus is None or not opus.is_available(src, tgt):
            return {"translated_text": text, "confidence": 0.0,
                    "translation_method": "opus_unavailable"}
        try:
            loop       = asyncio.get_event_loop()
            result     = await loop.run_in_executor(
                None,
                lambda: opus.translate(text, src, tgt),
            )
            if result and result.strip():
                logger.info(f"[OPUS] '{text}' ({src}ΓåÆ{tgt}) ΓåÆ '{result}'")
                return {"translated_text": result, "confidence": 1.0,
                        "translation_method": "opus_mt"}
        except Exception as e:
            logger.warning(f"[OPUS] Failed ({src}ΓåÆ{tgt}): {e}")
        return {"translated_text": text, "confidence": 0.0,
                "translation_method": "opus_failed"}

    # -----------------------------------------------------------------------
    # Internal pipeline steps (shared by all bul pairs + enΓåötl fallback)
    # -----------------------------------------------------------------------

    def _lookup_phrase(self, norm_phrase: str, lang_pair: str) -> Optional[str]:
        """
        Enhanced phrase lookup with normalization and source-documented fallback.
        
        First tries exact match, then checks sentence annotations for documented phrases.
        """
        # Try exact match first
        for translation, pair, _ in self.phrase_index.get(norm_phrase, []):
            if pair == lang_pair:
                return translation
        
        # If we have POS annotations, check for documented sentence matches
        if self.pos_annotations and 'sentence_annotations' in self.pos_annotations:
            return self._lookup_from_sentence_annotations(norm_phrase, lang_pair)
        
        return None
    
    def _lookup_from_sentence_annotations(
        self,
        norm_phrase: str,
        lang_pair: str
    ) -> Optional[str]:
        """
        Search sentence annotations for documented phrase translations.
        
        Uses corpus-grounded evidence from sentence.json.
        """
        sentences = self.pos_annotations.get('sentence_annotations', [])
        
        # Determine which fields to compare based on language pair
        if lang_pair == "bul_to_en":
            source_field, target_field = 'bulos', 'english'
        elif lang_pair == "en_to_bul":
            source_field, target_field = 'english', 'bulos'
        elif lang_pair == "bul_to_tl":
            source_field, target_field = 'bulos', 'filipino'
        elif lang_pair == "tl_to_bul":
            source_field, target_field = 'filipino', 'bulos'
        elif lang_pair == "en_to_tl":
            source_field, target_field = 'english', 'filipino'
        elif lang_pair == "tl_to_en":
            source_field, target_field = 'filipino', 'english'
        else:
            return None
        
        # Search for matching documented phrases
        for sentence in sentences:
            source_text = self._normalize_text(sentence.get(source_field, ''))
            
            if source_text == norm_phrase:
                # Exact documented match found
                target_text = sentence.get(target_field, '')
                if target_text:
                    logger.info(
                        f"[Corpus match] Found documented translation: "
                        f"'{norm_phrase}' → '{target_text}' "
                        f"(source: {sentence.get('sentence_id', 'unknown')})"
                    )
                    return target_text
        
        return None

    # Step 1 ΓÇö exact phrase match
    def _step1_phrase(self, text: str, lang_pair: str) -> Optional[Dict[str, Any]]:
        t = self._lookup_phrase(self._normalize_text(text), lang_pair)
        if t is not None:
            logger.debug(f"[Step 1] '{text}' ΓåÆ '{t}'")
            return {"translated_text": t, "confidence": 1.0,
                    "translation_method": "phrase_match"}
        return None

    # Step 2 ΓÇö greedy word match
    def _step2_word(self, text: str, lang_pair: str) -> Dict[str, Any]:
        words_raw  = text.split()
        words_norm = [self._normalize_text(w) for w in words_raw]

        if not words_norm:
            return {"translated_text": text, "confidence": 0.0,
                    "translation_method": "word_match", "parts": [],
                    "words_raw": words_raw, "words_norm": words_norm,
                    "unmatched_positions": []}

        parts, matched, unmatched = [], 0, []
        i = 0
        while i < len(words_norm):
            found_t, found_len = None, 0
            for length in range(len(words_norm) - i, 0, -1):
                phrase = " ".join(words_norm[i : i + length])
                t = self._lookup_phrase(phrase, lang_pair)
                if t is not None:
                    found_t, found_len = t, length
                    break
            if found_t is not None:
                parts.append(found_t)
                matched += found_len
                i += found_len
            else:
                parts.append(words_raw[i])
                unmatched.append(len(parts) - 1)
                i += 1

        total      = len(words_norm)
        confidence = matched / total if total > 0 else 0.0
        method     = ("word_match" if confidence == 1.0
                      else "word_match_partial" if confidence > 0 else "no_match")
        logger.info(f"[Step 2] confidence={confidence:.2f} ({matched}/{total})")
        return {"translated_text": " ".join(parts), "confidence": confidence,
                "translation_method": method, "parts": parts,
                "words_raw": words_raw, "words_norm": words_norm,
                "unmatched_positions": unmatched}

    # Step 3 / Step 4-bul ΓÇö fuzzy match with configurable threshold
    def _fuzzy_pass(
        self,
        step2_result: Dict[str, Any],
        lang_pair:    str,
        threshold:    float,
        step_label:   str,
    ) -> Dict[str, Any]:
        unmatched = step2_result.get("unmatched_positions", [])
        if not unmatched:
            return step2_result

        parts      = list(step2_result["parts"])
        words_norm = step2_result["words_norm"]
        words_raw  = step2_result["words_raw"]
        pair_keys  = [k for k, entries in self.phrase_index.items()
                      if " " not in k
                      and any(p == lang_pair for _, p, _ in entries)]
        newly = 0

        for pos in unmatched:
            if pos >= len(words_norm):
                continue
            token = words_norm[pos]
            if len(token) < FUZZY_MIN_LEN:
                continue

            best_key, best_score = None, 0.0
            for candidate in pair_keys:
                score = levenshtein_similarity(token, candidate)
                if score > best_score:
                    best_score, best_key = score, candidate

            if best_key and best_score >= threshold:
                t = self._lookup_phrase(best_key, lang_pair)
                if t:
                    logger.debug(
                        f"[{step_label}] '{words_raw[pos]}' Γëê '{best_key}' "
                        f"(score={best_score:.2f}) ΓåÆ '{t}'"
                    )
                    parts[pos] = t
                    newly += 1

        total         = len(words_norm)
        prev_matched  = int(round(step2_result["confidence"] * total))
        total_matched = prev_matched + newly
        confidence    = total_matched / total if total > 0 else 0.0
        method        = ("fuzzy_match" if confidence == 1.0
                         else "fuzzy_match_partial" if confidence > 0 else "no_match")
        logger.info(f"[{step_label}] resolved {newly}/{len(unmatched)} tokens, "
                    f"confidence={confidence:.2f}")
        return {"translated_text": " ".join(parts), "confidence": confidence,
                "translation_method": method,
                # pass along for potential next pass
                "parts": parts, "words_raw": words_raw,
                "words_norm": words_norm,
                "unmatched_positions": [p for p in unmatched
                                        if parts[p] == words_raw[p]]}

    # ΓöÇΓöÇ bul pipeline: phrase ΓåÆ word ΓåÆ fuzzy(0.75) ΓåÆ lenient fuzzy(0.50) ΓöÇΓöÇ

    async def _translate_bul_pipeline(
        self, text: str, src: str, tgt: str
    ) -> Dict[str, Any]:
        lang_pair = f"{src}_to_{tgt}"

        # Step 1
        r = self._step1_phrase(text, lang_pair)
        if r:
            logger.info("[bul pipeline] exit Step 1")
            return r

        # Step 2
        s2 = self._step2_word(text, lang_pair)
        if s2["confidence"] == 1.0:
            logger.info("[bul pipeline] exit Step 2")
            return {k: s2[k] for k in ("translated_text", "confidence", "translation_method")}

        # Step 3 ΓÇö strict fuzzy
        s3 = self._fuzzy_pass(s2, lang_pair, FUZZY_THRESHOLD, "Step 3")
        if s3["confidence"] == 1.0:
            logger.info("[bul pipeline] exit Step 3")
            return {k: s3[k] for k in ("translated_text", "confidence", "translation_method")}

        # Step 4 ΓÇö lenient fuzzy (OPUS has no Bulos support)
        logger.info("[bul pipeline] Step 4 ΓÇö lenient fuzzy")
        s4 = self._fuzzy_pass(s3, lang_pair, FUZZY_THRESHOLD_LENIENT, "Step 4")
        return {k: s4[k] for k in ("translated_text", "confidence", "translation_method")}

    # ΓöÇΓöÇ enΓåötl pipeline: Google ΓåÆ OPUS-MT ΓåÆ internal steps as last resort ΓöÇΓöÇ

    async def _translate_en_tl_pipeline(
        self, text: str, src: str, tgt: str
    ) -> Dict[str, Any]:

        # Try Google first (30 s cap so fallback kicks in quickly)
        try:
            gr = await asyncio.wait_for(
                self._translate_google(text, src, tgt), timeout=30
            )
        except asyncio.TimeoutError:
            gr = {"translated_text": text, "confidence": 0.0,
                  "translation_method": "google_timeout"}

        if gr["confidence"] > 0:
            return gr

        logger.info(f"[enΓåötl] Google unavailable ΓÇö trying OPUS-MT ({src}ΓåÆ{tgt})")

        # Try OPUS-MT
        opus = _get_opus()
        if opus and opus.is_available(src, tgt):
            or_ = await self._translate_opus(text, src, tgt)
            if or_["confidence"] > 0:
                return or_

        logger.info("[enΓåötl] OPUS-MT unavailable ΓÇö falling back to internal pipeline")

        # Last resort: run the internal pipeline
        lang_pair = f"{src}_to_{tgt}"
        r = self._step1_phrase(text, lang_pair)
        if r:
            return r
        s2 = self._step2_word(text, lang_pair)
        if s2["confidence"] == 1.0:
            return {k: s2[k] for k in ("translated_text", "confidence", "translation_method")}
        s3 = self._fuzzy_pass(s2, lang_pair, FUZZY_THRESHOLD, "Step 3")
        if s3["confidence"] == 1.0:
            return {k: s3[k] for k in ("translated_text", "confidence", "translation_method")}
        s4 = self._fuzzy_pass(s3, lang_pair, FUZZY_THRESHOLD_LENIENT, "Step 4")
        return {k: s4[k] for k in ("translated_text", "confidence", "translation_method")}

    # -----------------------------------------------------------------------
    # Grammar validation helper
    # -----------------------------------------------------------------------

    def _validate_with_grammar(
        self,
        original: str,
        translated: str,
        source_lang: str,
        target_lang: str,
    ) -> Dict[str, Any]:
        """
        Validate a translation against grammar rules.
        
        Returns:
            Dictionary with grammar_status and applied_rule fields
        """
        if not self.grammar_engine:
            return {
                "grammar_status": "no_engine",
                "applied_rule": None
            }
        
        # Grammar validation is only for Bulos translations
        if target_lang != "bul":
            return {
                "grammar_status": "not_applicable",
                "applied_rule": None
            }
        
        # Check if any validation rules are available
        validation_rules = self.grammar_engine.get_validation_rules()
        if not validation_rules:
            return {
                "grammar_status": "no_rules",
                "applied_rule": None
            }
        
        # Perform validation
        result = self.grammar_engine.validate_sentence(translated, source_lang="bul")
        
        if result.get("matched_rules"):
            return {
                "grammar_status": "verified",
                "applied_rule": result["matched_rules"][0] if result["matched_rules"] else None
            }
        
        return {
            "grammar_status": "unverified",
            "applied_rule": None
        }

    # -----------------------------------------------------------------------
    # Public translate()
    # -----------------------------------------------------------------------

    async def translate(
        self,
        text:            str,
        source_language: str,
        target_language: str,
        user_id:         Optional[str] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Translate: '{text}' ({source_language}ΓåÆ{target_language})")

        if source_language not in ("en", "tl", "bul"):
            raise ValueError(f"Invalid source_language: {source_language}")
        if (source_language, target_language) not in self.SUPPORTED_PAIRS:
            raise ValueError(
                f"Unsupported pair: {source_language}ΓåÆ{target_language}. "
                f"Supported: {self.SUPPORTED_PAIRS}"
            )
        if source_language == target_language:
            return {
                "original_text": text, "translated_text": text,
                "source_language": source_language,
                "target_language": target_language,
                "confidence": 1.0, "translation_method": "passthrough",
            }

        text = text.strip()
        if not text:
            return {
                "original_text": "", "translated_text": "",
                "source_language": source_language,
                "target_language": target_language,
                "confidence": 0.0, "translation_method": "empty_input",
            }

        try:
            if source_language in ("en", "tl") and target_language in ("en", "tl"):
                coro = self._translate_en_tl_pipeline(text, source_language, target_language)
            else:
                coro = self._translate_bul_pipeline(text, source_language, target_language)

            result = await asyncio.wait_for(coro, timeout=self.timeout)

        except asyncio.TimeoutError:
            logger.error(f"Translation timeout ({self.timeout}s) for: '{text}'")
            raise asyncio.TimeoutError(
                f"Translation exceeded timeout of {self.timeout} seconds"
            )

        # Validate with grammar rules
        grammar_info = self._validate_with_grammar(
            text, result["translated_text"], source_language, target_language
        )

        return {
            "original_text":      text,
            "translated_text":    result["translated_text"],
            "source_language":    source_language,
            "target_language":    target_language,
            "confidence":         result["confidence"],
            "translation_method": result.get("translation_method", "unknown"),
            "grammar_status":     grammar_info["grammar_status"],
            "applied_rule":       grammar_info["applied_rule"],
        }
