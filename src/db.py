"""
Module: db.py
Purpose: SQLite persistence for Finlyzer — complaints and call log tables.
"""

import os
import sqlite3
from typing import Optional, List, Dict

import pandas as pd


def get_db_path(base_dir: Optional[str] = None) -> str:
    """Return the absolute path to the SQLite database file."""
    base = base_dir or os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )
    data_dir = os.path.join(base, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "finlyzer.db")


def init_db(db_path: Optional[str] = None, csv_path: Optional[str] = None) -> str:
    """
    Create the complaints and calls tables if they do not exist.
    Optionally seed complaints from a CSV file.
    Returns the db_path used.
    """
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS complaints (
                Complaint_ID     TEXT PRIMARY KEY,
                Customer_ID      TEXT,
                Transaction_Date TEXT,
                Channel          TEXT,
                Amount           REAL,
                Complaint_Date   TEXT,
                Issue            TEXT,
                Status           TEXT,
                Resolution_Time  REAL,
                Customer_Email   TEXT,
                Phone            TEXT
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS calls (
                Call_ID       TEXT PRIMARY KEY,
                Complaint_ID  TEXT,
                Customer_ID   TEXT,
                Call_Date     TEXT,
                Agent         TEXT,
                Outcome       TEXT,
                Notes         TEXT,
                Escalated     INTEGER,
                Follow_Up_Date TEXT
            )"""
        )
        conn.commit()

        if csv_path:
            csv_full = (
                csv_path
                if os.path.isabs(csv_path)
                else os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "..", csv_path)
                )
            )
            if os.path.exists(csv_full):
                df = pd.read_csv(csv_full)
                expected = {
                    "Complaint_ID", "Customer_ID", "Transaction_Date",
                    "Channel", "Amount", "Complaint_Date", "Issue",
                    "Status", "Resolution_Time",
                }
                for col in expected:
                    if col not in df.columns:
                        df[col] = None
                if "Customer_Email" not in df.columns:
                    df["Customer_Email"] = ""
                if "Phone" not in df.columns:
                    df["Phone"] = ""
                df.to_sql("complaints", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    return db_path


def get_all_complaints(db_path: Optional[str] = None) -> pd.DataFrame:
    """Return all complaints from the database."""
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT * FROM complaints",
            conn,
            parse_dates=["Transaction_Date", "Complaint_Date"],
        )
    finally:
        conn.close()


def get_filtered_complaints(
    db_path: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    channels: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    search: Optional[str] = None,
) -> pd.DataFrame:
    """Return complaints filtered by date range, channel, status, and keyword."""
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        q = "SELECT * FROM complaints WHERE 1=1"
        params: List = []
        if start_date:
            q += " AND date(Complaint_Date) >= date(?)"
            params.append(start_date)
        if end_date:
            q += " AND date(Complaint_Date) <= date(?)"
            params.append(end_date)
        if channels:
            q += " AND Channel IN ({})".format(",".join("?" for _ in channels))
            params.extend(channels)
        if statuses:
            q += " AND Status IN ({})".format(",".join("?" for _ in statuses))
            params.extend(statuses)
        if search:
            q += " AND Issue LIKE ?"
            params.append(f"%{search}%")
        return pd.read_sql_query(
            q, conn, params=params,
            parse_dates=["Transaction_Date", "Complaint_Date"],
        )
    finally:
        conn.close()


def update_complaints_bulk(updates: pd.DataFrame, db_path: Optional[str] = None):
    """Bulk-update complaint fields in the database."""
    db_path = db_path or get_db_path()
    if updates.empty:
        return
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        for _, row in updates.iterrows():
            cid = row.get("Complaint_ID")
            if not cid:
                continue
            set_parts = []
            params = []
            for col in ("Status", "Channel", "Resolution_Time", "Customer_Email", "Phone"):
                if col in row and pd.notna(row[col]):
                    set_parts.append(f"{col} = ?")
                    params.append(row[col])
            if not set_parts:
                continue
            params.append(cid)
            cur.execute(
                f"UPDATE complaints SET {', '.join(set_parts)} WHERE Complaint_ID = ?",
                params,
            )
        conn.commit()
    finally:
        conn.close()


def log_call(call: Dict, db_path: Optional[str] = None):
    """Append a call record to the calls table."""
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.DataFrame([call])
        if "Escalated" in df.columns:
            df["Escalated"] = df["Escalated"].astype(int)
        df.to_sql("calls", conn, if_exists="append", index=False)
    finally:
        conn.close()


def get_calls(
    db_path: Optional[str] = None,
    complaint_id: Optional[str] = None,
) -> pd.DataFrame:
    """Return call records, optionally filtered by complaint ID."""
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        if complaint_id:
            return pd.read_sql_query(
                "SELECT * FROM calls WHERE Complaint_ID = ? ORDER BY Call_Date DESC",
                conn,
                params=(complaint_id,),
            )
        return pd.read_sql_query(
            "SELECT * FROM calls ORDER BY Call_Date DESC", conn
        )
    finally:
        conn.close()


if __name__ == "__main__":
    # Run directly to initialise and seed the database:
    # python -m src.db
    print(init_db(csv_path="data/failed_transactions.csv"))
