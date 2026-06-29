"""
Module: nlp_engine.py
Purpose: NLP tasks — sentiment analysis, topic modeling (LDA), keyword extraction.
"""

from __future__ import annotations
from typing import Optional

_sentiment_analyzer = None


def _get_sentiment_analyzer():
    """Lazy-load sentiment pipeline on first use, not at import time."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        from transformers import pipeline
        _sentiment_analyzer = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english",
            truncation=True,
            max_length=512,
        )
    return _sentiment_analyzer


def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of input text.
    Returns dict with 'label' (POSITIVE/NEGATIVE) and 'score' (0.0–1.0).
    Falls back to NEUTRAL on error so the app never crashes on bad input.
    """
    if not text or not str(text).strip():
        return {"label": "NEUTRAL", "score": 0.0}
    try:
        analyzer = _get_sentiment_analyzer()
        result = analyzer(str(text)[:512])
        return result[0] if result else {"label": "NEUTRAL", "score": 0.0}
    except Exception:
        return {"label": "NEUTRAL", "score": 0.0}


def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    """
    Extract top N keywords using TF-IDF scoring.
    Lightweight — no external model required.
    """
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not text or not str(text).strip():
        return []
    try:
        vec = TfidfVectorizer(stop_words="english", max_features=200)
        vec.fit([text])
        scores = vec.idf_
        terms = vec.get_feature_names_out()
        top_idx = np.argsort(scores)[:top_n]
        return [terms[i] for i in top_idx]
    except Exception:
        return []


def run_lda(texts: list[str], n_topics: int = 5, n_keywords: int = 6) -> list[dict]:
    """
    Run Latent Dirichlet Allocation topic modeling on a list of complaint texts.

    Returns a list of topic dicts:
        [{"topic_id": 0, "keywords": ["transfer", "delay", "account", ...]}, ...]
    """
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.decomposition import LatentDirichletAllocation
    import numpy as np

    if not texts or len(texts) < n_topics:
        return []

    try:
        vec = CountVectorizer(
            max_df=0.95,
            min_df=2,
            stop_words="english",
            max_features=1000,
        )
        X = vec.fit_transform(texts)
        if X.shape[0] < n_topics:
            n_topics = max(2, X.shape[0])

        lda = LatentDirichletAllocation(
            n_components=n_topics,
            random_state=42,
            max_iter=10,
        )
        lda.fit(X)

        feature_names = vec.get_feature_names_out()
        topics = []
        for topic_id, topic in enumerate(lda.components_):
            top_idx = topic.argsort()[: -n_keywords - 1 : -1]
            keywords = [feature_names[i] for i in top_idx]
            topics.append({"topic_id": topic_id, "keywords": keywords})
        return topics
    except Exception:
        return []


def get_complaint_topic(text: str, topics: list[dict]) -> Optional[str]:
    """
    Given a preprocessed complaint text and a list of LDA topics,
    return the most likely topic label (its top keywords joined as a string).
    Simple keyword overlap heuristic — fast, no model needed.
    """
    if not text or not topics:
        return None
    text_lower = text.lower()
    best_topic = None
    best_score = 0
    for t in topics:
        score = sum(1 for kw in t["keywords"] if kw in text_lower)
        if score > best_score:
            best_score = score
            best_topic = " / ".join(t["keywords"][:3])
    return best_topic
