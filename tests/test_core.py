"""
Core unit tests for Finlyzer.
Run with: python -m pytest tests/ -v
"""

import os
import pytest
import pandas as pd
import tempfile

from src.preprocessing import clean_text, preprocess_text, anonymize_pii
from src.clustering import cluster_texts
from src.nlp_engine import extract_keywords, run_lda, get_complaint_topic
from src.utils import atomic_write_csv, atomic_write_json
from src.data_input import load_data


# ---------------------------------------------------------------------------
# preprocessing tests
# ---------------------------------------------------------------------------

def test_clean_text_basic():
    assert clean_text("Hello, World! 123") == "hello world 123"


def test_clean_text_empty_string():
    assert clean_text("") == ""


def test_clean_text_none():
    assert clean_text(None) == ""


def test_clean_text_strips_special_chars():
    assert clean_text("ATM failure!!!") == "atm failure"


def test_preprocess_text_returns_string():
    result = preprocess_text("The customer could not withdraw funds from the ATM")
    assert isinstance(result, str)


def test_preprocess_text_empty():
    assert preprocess_text("") == ""


def test_preprocess_text_none():
    assert preprocess_text(None) == ""


def test_anonymize_pii_phone():
    result = anonymize_pii("Call 08034567890 for help")
    assert "08034567890" not in result


def test_anonymize_pii_account_number():
    result = anonymize_pii("Account 1234567890 was debited")
    assert "1234567890" not in result


# ---------------------------------------------------------------------------
# clustering tests
# ---------------------------------------------------------------------------

def test_cluster_texts_basic():
    texts = [
        "failed ATM transaction withdrawal",
        "card declined at point of sale",
        "online transfer returned error code",
        "mobile app login not working",
        "account frozen without notice",
        "wrong debit on account statement",
    ]
    labels = cluster_texts(texts, n_clusters=2)
    assert len(labels) == len(texts)
    assert all(isinstance(label, int) for label in labels)


def test_cluster_texts_empty():
    assert cluster_texts([]) == []


def test_cluster_texts_single_item():
    labels = cluster_texts(["only one complaint"], n_clusters=5)
    assert labels == [0]


def test_cluster_texts_none_values():
    labels = cluster_texts([None, "valid complaint text", None], n_clusters=2)
    assert len(labels) == 3


def test_cluster_count_never_exceeds_samples():
    texts = ["complaint one", "complaint two"]
    labels = cluster_texts(texts, n_clusters=10)
    assert max(labels) < len(texts)


# ---------------------------------------------------------------------------
# nlp_engine tests
# ---------------------------------------------------------------------------

def test_extract_keywords_returns_list():
    keywords = extract_keywords("The ATM failed to dispense cash after debit", top_n=3)
    assert isinstance(keywords, list)
    assert len(keywords) <= 3


def test_extract_keywords_empty():
    result = extract_keywords("")
    assert result == []


def test_run_lda_returns_topics():
    texts = [
        "ATM failed to dispense cash",
        "card declined at merchant terminal",
        "transfer delayed for three days",
        "mobile app login keeps failing",
        "wrong amount debited from account",
        "loan repayment not reflected",
        "account blocked without warning",
    ]
    topics = run_lda(texts, n_topics=2, n_keywords=3)
    assert isinstance(topics, list)
    if topics:  # may be empty if fewer texts than topics
        assert "keywords" in topics[0]
        assert isinstance(topics[0]["keywords"], list)


def test_run_lda_empty_input():
    assert run_lda([]) == []


def test_get_complaint_topic():
    topics = [
        {"topic_id": 0, "keywords": ["transfer", "delay", "account"]},
        {"topic_id": 1, "keywords": ["atm", "cash", "dispense"]},
    ]
    result = get_complaint_topic("ATM failed to dispense cash", topics)
    assert result is not None


# ---------------------------------------------------------------------------
# utils tests
# ---------------------------------------------------------------------------

def test_atomic_write_csv():
    df = pd.DataFrame({"A": [1, 2], "B": ["x", "y"]})
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.csv")
        atomic_write_csv(df, path)
        assert os.path.exists(path)
        loaded = pd.read_csv(path)
        assert list(loaded.columns) == ["A", "B"]
        assert len(loaded) == 2


def test_atomic_write_json():
    obj = {"key": "value", "count": 42}
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.json")
        atomic_write_json(obj, path)
        assert os.path.exists(path)
        import json
        with open(path) as f:
            loaded = json.load(f)
        assert loaded["key"] == "value"


# ---------------------------------------------------------------------------
# data_input tests
# ---------------------------------------------------------------------------

def test_load_data_csv():
    df = pd.DataFrame({
        "Complaint_ID": ["C001"],
        "Issue": ["ATM failure"],
        "Status": ["Pending"],
    })
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.csv")
        df.to_csv(path, index=False)
        loaded = load_data(path)
        assert len(loaded) == 1
        assert "Complaint_ID" in loaded.columns


def test_load_data_unsupported_format():
    with pytest.raises(ValueError, match="Unsupported file format"):
        load_data("complaints.txt")
