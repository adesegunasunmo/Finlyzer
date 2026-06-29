"""
Module: utils.py
Purpose: Utility functions — atomic file writes, logging setup.
"""

import logging
import tempfile
import os
import json


def setup_logger(name: str = "Finlyzer") -> logging.Logger:
    """Return a configured logger for the given name."""
    logging.basicConfig(level=logging.INFO)
    return logging.getLogger(name)


def atomic_write_csv(df, path: str):
    """
    Write a DataFrame to CSV atomically.
    Writes to a temp file first, then renames — prevents data corruption
    if the process is interrupted mid-write.
    """
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dirpath or ".", prefix="tmp_", suffix=".csv")
    os.close(fd)
    try:
        df.to_csv(tmp_path, index=False)
        os.replace(tmp_path, path)
    except Exception:
        logging.exception("Failed to atomically write CSV to %s", path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def atomic_write_json(obj, path: str):
    """
    Write a JSON-serializable object atomically.
    Same temp-file-then-rename pattern as atomic_write_csv.
    """
    dirpath = os.path.dirname(path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dirpath or ".", prefix="tmp_", suffix=".json")
    os.close(fd)
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        logging.exception("Failed to atomically write JSON to %s", path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
