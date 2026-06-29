"""
Module: preprocessing.py
Purpose: Clean, normalize, and prepare complaint text for NLP analysis.
"""

import re

_nlp = None


def _get_nlp():
    """Lazy-load spaCy model on first use to avoid crash at import time."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_web_sm")
        except (OSError, ModuleNotFoundError):
            # spaCy not installed or model not downloaded — use regex fallback
            _nlp = False
    return _nlp


def clean_text(text: str) -> str:
    """Basic text cleaning: lowercase, remove special characters."""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def preprocess_text(text: str) -> str:
    """
    Full preprocessing pipeline:
    1. Clean text (lowercase, strip special chars)
    2. Lemmatize and remove stopwords via spaCy (if available)
    Falls back to clean_text only if spaCy model not available.
    """
    text = clean_text(text)
    if not text:
        return ""

    nlp = _get_nlp()
    if not nlp:
        # spaCy unavailable — return cleaned text as-is
        return text

    doc = nlp(text)
    tokens = [
        token.lemma_
        for token in doc
        if not token.is_stop and not token.is_punct and token.lemma_.strip()
    ]
    return " ".join(tokens)


def anonymize_pii(text: str) -> str:
    """
    Redact personally identifiable information before storing or displaying.
    Replaces detected entities with safe placeholders.
    """
    if not text:
        return ""

    nlp = _get_nlp()
    if not nlp:
        # Fallback: regex-based redaction for common PII patterns
        text = re.sub(r"\b\d{10,}\b", "[ACCOUNT_NUMBER]", text)
        text = re.sub(r"\b0\d{10}\b", "[PHONE]", text)
        return text

    doc = nlp(text)
    redacted = text
    for ent in reversed(doc.ents):
        if ent.label_ in ("PERSON",):
            redacted = redacted[:ent.start_char] + "[CUSTOMER]" + redacted[ent.end_char:]
        elif ent.label_ in ("CARDINAL", "MONEY") and len(ent.text) >= 8:
            redacted = redacted[:ent.start_char] + "[ACCOUNT_NUMBER]" + redacted[ent.end_char:]
    # Phone numbers via regex (spaCy doesn't tag these reliably)
    redacted = re.sub(r"\b0\d{10}\b", "[PHONE]", redacted)
    redacted = re.sub(r"\b\d{10,16}\b", "[ACCOUNT_NUMBER]", redacted)
    return redacted
