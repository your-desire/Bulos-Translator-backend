"""
LSTM Seq2Seq Translation Service
=================================
Loads the trained LSTM models from models/lstm/<direction>/ and serves
them as Step 5 of the Bulos translation pipeline.

Expected files per direction:
  models/lstm/bul_en/
    model.keras          ← trained Keras model
    src_tokenizer.json   ← character-level source tokenizer
    tgt_tokenizer.json   ← word-level target tokenizer

Architecture (matches Bulos_LSTM_Training_Ready.ipynb):
  Source: character-level tokenization (preserves Bulos accents)
  Target: word-level tokenization with <start>/<end> tokens
  Model:  Encoder-decoder LSTM (256 units, embedding dim 128)

Only Bulos-related pairs are served — en↔tl is handled by OPUS-MT.
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import Optional

import numpy as np

from utils.logging_config import get_logger

logger = get_logger(__name__)

MODELS_DIR = Path(__file__).parent.parent / "models" / "lstm"

# Directions served by this service (en↔tl handled by OPUS-MT)
BUL_DIRECTIONS = ["bul_en", "en_bul", "bul_tl", "tl_bul"]

MAX_SOURCE_LEN = 128
MAX_TARGET_LEN = 50
START_TOKEN    = "<start>"
END_TOKEN      = "<end>"
PAD_TOKEN      = "<pad>"
UNK_TOKEN      = "<unk>"


class LSTMTranslator:
    """
    Loads and serves word-level LSTM translation models for Bulos pairs.
    Falls back gracefully if a model or tokenizer file is missing.
    """

    def __init__(self):
        self._models:    dict = {}
        self._available: set  = set()
        self.per_key_errors:  dict = {}

    # ── Loading ────────────────────────────────────────────────────────────

    def load_models(self) -> None:
        try:
            import tensorflow as tf
            keras = tf.keras
            from tensorflow.keras.preprocessing.text import tokenizer_from_json
            from tensorflow.keras.preprocessing.sequence import pad_sequences
        except ImportError as e:
            logger.warning(f"[LSTM] TensorFlow not installed: {e}")
            return

        loaded = 0
        for key in BUL_DIRECTIONS:
            model_dir  = MODELS_DIR / key
            model_path = model_dir / "model.keras"
            src_tok_p  = model_dir / "src_tokenizer.json"
            tgt_tok_p  = model_dir / "tgt_tokenizer.json"

            if not model_path.exists():
                logger.debug(f"[LSTM] model.keras not found for {key} — skipping")
                continue
            if not src_tok_p.exists() or not tgt_tok_p.exists():
                logger.warning(f"[LSTM] Tokenizer(s) missing for {key} — skipping")
                continue

            try:
                logger.info(f"[LSTM] Loading {key} ...")
                model = keras.models.load_model(str(model_path), compile=False)

                with open(src_tok_p, encoding="utf-8") as f:
                    src_tok = tokenizer_from_json(f.read())
                with open(tgt_tok_p, encoding="utf-8") as f:
                    tgt_tok = tokenizer_from_json(f.read())

                enc_model, dec_model = _build_inference_models(model, keras)

                self._models[key] = {
                    "enc":     enc_model,
                    "dec":     dec_model,
                    "src_tok": src_tok,
                    "tgt_tok": tgt_tok,
                    "pad_sequences": pad_sequences,
                }
                self._available.add(key)
                loaded += 1
                logger.info(f"[LSTM] Loaded: {key} "
                            f"(src_vocab={len(src_tok.word_index)}, "
                            f"tgt_vocab={len(tgt_tok.word_index)})")

            except Exception as e:
                err = traceback.format_exc()
                self.per_key_errors[key] = err
                logger.warning(f"[LSTM] Failed to load {key}: {e}\n{err}")

        logger.info(
            f"[LSTM] Ready — {loaded}/{len(BUL_DIRECTIONS)} models loaded. "
            f"Available: {sorted(self._available)}"
        )

    # ── Public interface ───────────────────────────────────────────────────

    def is_available(self, src_lang: str, tgt_lang: str) -> bool:
        return f"{src_lang}_{tgt_lang}" in self._available

    def translate(self, text: str, src_lang: str, tgt_lang: str) -> Optional[str]:
        """
        Translate text using the LSTM model.
        Returns the translated string, or None on failure.
        """
        key = f"{src_lang}_{tgt_lang}"
        if key not in self._available:
            return None

        try:
            entry        = self._models[key]
            src_tok      = entry["src_tok"]
            tgt_tok      = entry["tgt_tok"]
            pad_sequences = entry["pad_sequences"]

            src_seq = src_tok.texts_to_sequences([text])
            src_seq = pad_sequences(src_seq, maxlen=MAX_SOURCE_LEN,
                                    padding="post", truncating="post")

            result = _decode_sequence(
                src_seq,
                entry["enc"],
                entry["dec"],
                tgt_tok,
            )
            return result if result.strip() else None

        except Exception as e:
            logger.error(f"[LSTM] translate failed ({key}): {e}", exc_info=True)
            return None

    @property
    def available_directions(self) -> list:
        return sorted(self._available)


# ── Module-level singleton ────────────────────────────────────────────────
_instance: Optional[LSTMTranslator] = None


def get_lstm_translator() -> LSTMTranslator:
    global _instance
    if _instance is None:
        _instance = LSTMTranslator()
        _instance.load_models()
    return _instance


# ── Inference helpers ─────────────────────────────────────────────────────

def _build_inference_models(training_model, keras):
    """
    Split the trained seq2seq model into standalone encoder and decoder
    using the named layers defined in Bulos_LSTM_Training_Ready.ipynb.
    """
    from tensorflow.keras import layers as klayers

    encoder_inputs = training_model.input[0]
    _, state_h, state_c = training_model.get_layer("encoder_lstm").output
    encoder_model  = keras.Model(encoder_inputs, [state_h, state_c])

    decoder_inputs = training_model.input[1]
    lstm_units     = training_model.get_layer("encoder_lstm").units
    dec_h_in       = klayers.Input(shape=(lstm_units,), name="inf_dec_h")
    dec_c_in       = klayers.Input(shape=(lstm_units,), name="inf_dec_c")

    dec_emb   = training_model.get_layer("decoder_embedding")
    dec_lstm  = training_model.get_layer("decoder_lstm")
    dec_dense = training_model.get_layer("decoder_dense")

    dec_embedded          = dec_emb(decoder_inputs)
    dec_out, new_h, new_c = dec_lstm(
        dec_embedded, initial_state=[dec_h_in, dec_c_in]
    )
    dec_out    = dec_dense(dec_out)

    decoder_model = keras.Model(
        [decoder_inputs, dec_h_in, dec_c_in],
        [dec_out, new_h, new_c]
    )
    return encoder_model, decoder_model


def _decode_sequence(
    src_seq:      np.ndarray,
    encoder_model,
    decoder_model,
    tgt_tokenizer,
    max_length:   int = MAX_TARGET_LEN,
) -> str:
    """Greedy autoregressive decoding."""
    states   = encoder_model.predict(src_seq, verbose=0)
    start_id = tgt_tokenizer.word_index.get(START_TOKEN)
    end_id   = tgt_tokenizer.word_index.get(END_TOKEN)

    if start_id is None or end_id is None:
        return ""

    target_seq = np.zeros((1, 1))
    target_seq[0, 0] = start_id
    decoded = []

    for _ in range(max_length):
        out_tokens, h, c = decoder_model.predict(
            [target_seq, states[0], states[1]], verbose=0
        )
        idx  = int(np.argmax(out_tokens[0, -1, :]))
        if idx == end_id:
            break
        word = tgt_tokenizer.index_word.get(idx, "")
        if word and word not in (START_TOKEN, END_TOKEN, PAD_TOKEN, UNK_TOKEN):
            decoded.append(word)
        target_seq[0, 0] = idx
        states = [h, c]

    return " ".join(decoded)
