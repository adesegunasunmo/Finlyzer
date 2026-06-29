"""
Module: data_input.py
Purpose: Ingest banking complaint data from CSV or Excel files.
"""

import pandas as pd


def load_data(filepath: str) -> pd.DataFrame:
    """
    Load complaint data from a CSV or Excel file.

    Args:
        filepath: path to .csv or .xlsx file

    Returns:
        DataFrame with complaint records

    Raises:
        ValueError: if the file format is not supported
        FileNotFoundError: if the file does not exist
    """
    if filepath.endswith(".csv"):
        return pd.read_csv(filepath)
    elif filepath.endswith(".xlsx"):
        return pd.read_excel(filepath)
    else:
        raise ValueError(f"Unsupported file format: {filepath}. Use .csv or .xlsx")
