"""
Module: db.py
Purpose: SQLite persistence for Finlyzer — complaints, calls, chat, users, audit tables.
"""

import os
import sqlite3
import hashlib
import secrets
from typing import Optional, List, Dict

import pandas as pd


def get_db_path(base_dir: Optional[str] = None) -> str:
    base = base_dir or os.path.abspath(
        os.path.join(os.path.dirname(__file__), ".."))
    data_dir = os.path.join(base, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "finlyzer.db")


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 100_000).hex()
    return hashed, salt


def init_db(db_path: Optional[str] = None, csv_path: Optional[str] = None) -> str:
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS complaints (
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
                Phone            TEXT,
                Assigned_Agent   TEXT,
                SLA_Hours        REAL DEFAULT 48
            );

            CREATE TABLE IF NOT EXISTS calls (
                Call_ID        TEXT PRIMARY KEY,
                Complaint_ID   TEXT,
                Customer_ID    TEXT,
                Call_Date      TEXT,
                Agent          TEXT,
                Outcome        TEXT,
                Notes          TEXT,
                Escalated      INTEGER,
                Follow_Up_Date TEXT
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                Message_ID   TEXT PRIMARY KEY,
                Complaint_ID TEXT,
                Sender       TEXT,
                Role         TEXT,
                Message      TEXT,
                Timestamp    TEXT,
                Read_By      TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS users (
                Username     TEXT PRIMARY KEY,
                Password_Hash TEXT,
                Salt         TEXT,
                Role         TEXT DEFAULT 'viewer',
                Email        TEXT,
                Full_Name    TEXT,
                Created_At   TEXT,
                Last_Login   TEXT,
                Active       INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                Log_ID    TEXT PRIMARY KEY,
                Timestamp TEXT,
                Username  TEXT,
                Role      TEXT,
                Action    TEXT,
                Details   TEXT,
                IP        TEXT
            );
        """)
        conn.commit()

        if csv_path:
            csv_full = csv_path if os.path.isabs(csv_path) else os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", csv_path))
            if os.path.exists(csv_full):
                df = pd.read_csv(csv_full)
                for col in ["Complaint_ID", "Customer_ID", "Transaction_Date", "Channel",
                            "Amount", "Complaint_Date", "Issue", "Status", "Resolution_Time"]:
                    if col not in df.columns:
                        df[col] = None
                for col in ["Customer_Email", "Phone", "Assigned_Agent"]:
                    if col not in df.columns:
                        df[col] = ""
                if "SLA_Hours" not in df.columns:
                    df["SLA_Hours"] = 48
                df.to_sql("complaints", conn, if_exists="replace", index=False)
    finally:
        conn.close()
    return db_path


# ── Complaints ────────────────────────────────────────────────────────────────

def get_all_complaints(db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query("SELECT * FROM complaints", conn,
                                 parse_dates=["Transaction_Date", "Complaint_Date"])
    finally:
        conn.close()


def update_complaints_bulk(updates: pd.DataFrame, db_path: Optional[str] = None):
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
            set_parts, params = [], []
            for col in ("Status", "Channel", "Resolution_Time", "Customer_Email",
                        "Phone", "Assigned_Agent", "SLA_Hours"):
                if col in row and pd.notna(row[col]):
                    set_parts.append(f"{col} = ?")
                    params.append(row[col])
            if not set_parts:
                continue
            params.append(cid)
            cur.execute(
                f"UPDATE complaints SET {', '.join(set_parts)} WHERE Complaint_ID = ?", params)
        conn.commit()
    finally:
        conn.close()


def assign_complaint(complaint_id: str, agent: str, db_path: Optional[str] = None):
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("UPDATE complaints SET Assigned_Agent = ? WHERE Complaint_ID = ?",
                     (agent, complaint_id))
        conn.commit()
    finally:
        conn.close()


# ── Calls ─────────────────────────────────────────────────────────────────────

def log_call(call: Dict, db_path: Optional[str] = None):
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        df = pd.DataFrame([call])
        if "Escalated" in df.columns:
            df["Escalated"] = df["Escalated"].astype(int)
        df.to_sql("calls", conn, if_exists="append", index=False)
    finally:
        conn.close()


def get_calls(db_path: Optional[str] = None, complaint_id: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        if complaint_id:
            return pd.read_sql_query(
                "SELECT * FROM calls WHERE Complaint_ID = ? ORDER BY Call_Date DESC",
                conn, params=(complaint_id,))
        return pd.read_sql_query("SELECT * FROM calls ORDER BY Call_Date DESC", conn)
    finally:
        conn.close()


# ── Chat ──────────────────────────────────────────────────────────────────────

def send_chat_message(complaint_id: str, sender: str, role: str,
                      message: str, db_path: Optional[str] = None):
    import uuid
    from datetime import datetime
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO chat_messages VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), complaint_id, sender, role,
             message, datetime.utcnow().isoformat(), "")
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_messages(complaint_id: str, db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT * FROM chat_messages WHERE Complaint_ID = ? ORDER BY Timestamp ASC",
            conn, params=(complaint_id,))
    finally:
        conn.close()


def get_all_chat(db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT * FROM chat_messages ORDER BY Timestamp DESC LIMIT 200", conn)
    finally:
        conn.close()


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(username: str, password: str, role: str = "viewer",
                email: str = "", full_name: str = "",
                db_path: Optional[str] = None) -> bool:
    from datetime import datetime
    db_path = db_path or get_db_path()
    hashed, salt = _hash_password(password)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?)",
            (username, hashed, salt, role, email, full_name,
             datetime.utcnow().isoformat(), None, 1)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def verify_user(username: str, password: str,
                db_path: Optional[str] = None) -> Optional[Dict]:
    from datetime import datetime
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.execute(
            "SELECT * FROM users WHERE Username = ? AND Active = 1", (username,))
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        user = dict(zip(cols, row))
        hashed, _ = _hash_password(password, user["Salt"])
        if hashed != user["Password_Hash"]:
            return None
        conn.execute("UPDATE users SET Last_Login = ? WHERE Username = ?",
                     (datetime.utcnow().isoformat(), username))
        conn.commit()
        return user
    finally:
        conn.close()


def change_password(username: str, old_password: str, new_password: str,
                    db_path: Optional[str] = None) -> tuple[bool, str]:
    db_path = db_path or get_db_path()
    user = verify_user(username, old_password, db_path)
    if not user:
        return False, "Current password is incorrect."
    if len(new_password) < 8:
        return False, "New password must be at least 8 characters."
    if not any(c.isupper() for c in new_password):
        return False, "New password needs at least one uppercase letter."
    if not any(c.isdigit() for c in new_password):
        return False, "New password needs at least one number."
    hashed, salt = _hash_password(new_password)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET Password_Hash = ?, Salt = ? WHERE Username = ?",
            (hashed, salt, username))
        conn.commit()
        return True, "Password changed successfully."
    finally:
        conn.close()


def get_all_users(db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT Username, Role, Email, Full_Name, Created_At, Last_Login, Active FROM users",
            conn)
    finally:
        conn.close()


def deactivate_user(username: str, db_path: Optional[str] = None):
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET Active = 0 WHERE Username = ?", (username,))
        conn.commit()
    finally:
        conn.close()


def reactivate_user(username: str, db_path: Optional[str] = None):
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE users SET Active = 1 WHERE Username = ?", (username,))
        conn.commit()
    finally:
        conn.close()


# ── Audit log ─────────────────────────────────────────────────────────────────

def write_audit(username: str, role: str, action: str,
                details: str, ip: str = "unknown",
                db_path: Optional[str] = None):
    import uuid
    from datetime import datetime
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO audit_log VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), datetime.utcnow().isoformat(),
             username, role, action, details, ip))
        conn.commit()
    finally:
        conn.close()


def get_audit_log(limit: int = 200, db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            f"SELECT * FROM audit_log ORDER BY Timestamp DESC LIMIT {limit}", conn)
    finally:
        conn.close()


# ── Export ────────────────────────────────────────────────────────────────────

def export_complaints_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def export_complaints_excel(df: pd.DataFrame) -> bytes:
    import io
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name="Complaints")
    return buf.getvalue()


if __name__ == "__main__":
    print(init_db(csv_path="data/failed_transactions.csv"))


# ── IT Incidents & System Status ──────────────────────────────────────────────

def init_extra_tables(db_path: Optional[str] = None):
    """Add IT incidents, system status, and notifications tables."""
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS it_incidents (
                Incident_ID   TEXT PRIMARY KEY,
                Created_At    TEXT,
                Created_By    TEXT,
                Cluster_Key   TEXT,
                Title         TEXT,
                Description   TEXT,
                Affected_Channel TEXT,
                Complaint_IDs TEXT,
                Status        TEXT DEFAULT 'Open',
                Severity      TEXT DEFAULT 'Medium',
                Resolved_At   TEXT,
                Resolved_By   TEXT,
                Resolution_Note TEXT
            );

            CREATE TABLE IF NOT EXISTS system_status (
                Component_ID  TEXT PRIMARY KEY,
                Component_Name TEXT,
                Status        TEXT DEFAULT 'Operational',
                Message       TEXT DEFAULT '',
                Updated_At    TEXT,
                Updated_By    TEXT
            );

            CREATE TABLE IF NOT EXISTS notifications (
                Notif_ID      TEXT PRIMARY KEY,
                Complaint_ID  TEXT,
                Customer_ID   TEXT,
                Channel       TEXT,
                Message       TEXT,
                Sent_At       TEXT,
                Status        TEXT DEFAULT 'Pending'
            );

            CREATE TABLE IF NOT EXISTS customer_profiles (
                Customer_ID   TEXT PRIMARY KEY,
                Full_Name     TEXT,
                Phone         TEXT,
                Email         TEXT,
                Account_Type  TEXT,
                Branch        TEXT,
                Risk_Level    TEXT DEFAULT 'Normal'
            );
        """)
        conn.commit()
    finally:
        conn.close()


def create_it_incident(title: str, description: str, cluster_key: str,
                       affected_channel: str, complaint_ids: list,
                       severity: str, created_by: str,
                       db_path: Optional[str] = None) -> str:
    import uuid
    from datetime import datetime
    db_path = db_path or get_db_path()
    incident_id = str(uuid.uuid4())[:8].upper()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO it_incidents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (incident_id, datetime.utcnow().isoformat(), created_by,
             cluster_key, title, description, affected_channel,
             ",".join(complaint_ids), "Open", severity, None, None, None))
        conn.commit()
    finally:
        conn.close()
    return incident_id


def get_it_incidents(db_path: Optional[str] = None, status: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        q = "SELECT * FROM it_incidents"
        params = []
        if status:
            q += " WHERE Status = ?"
            params.append(status)
        q += " ORDER BY Created_At DESC"
        return pd.read_sql_query(q, conn, params=params)
    finally:
        conn.close()


def resolve_it_incident(incident_id: str, resolved_by: str,
                        resolution_note: str, db_path: Optional[str] = None):
    from datetime import datetime
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "UPDATE it_incidents SET Status=?, Resolved_At=?, Resolved_By=?, Resolution_Note=? WHERE Incident_ID=?",
            ("Resolved", datetime.utcnow().isoformat(), resolved_by, resolution_note, incident_id))
        conn.commit()
    finally:
        conn.close()


def get_system_status(db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query("SELECT * FROM system_status ORDER BY Component_Name", conn)
    finally:
        conn.close()


def update_system_status(component_id: str, component_name: str,
                         status: str, message: str, updated_by: str,
                         db_path: Optional[str] = None):
    from datetime import datetime
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO system_status VALUES (?,?,?,?,?,?)",
            (component_id, component_name, status, message,
             datetime.utcnow().isoformat(), updated_by))
        conn.commit()
    finally:
        conn.close()


def log_notification(complaint_id: str, customer_id: str,
                     channel: str, message: str,
                     db_path: Optional[str] = None):
    import uuid
    from datetime import datetime
    db_path = db_path or get_db_path()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT INTO notifications VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), complaint_id, customer_id,
             channel, message, datetime.utcnow().isoformat(), "Sent"))
        conn.commit()
    finally:
        conn.close()


def get_notifications(db_path: Optional[str] = None) -> pd.DataFrame:
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        return pd.read_sql_query(
            "SELECT * FROM notifications ORDER BY Sent_At DESC LIMIT 100", conn)
    finally:
        conn.close()


def detect_spikes(db_path: Optional[str] = None,
                  window_hours: float = 2.0,
                  threshold: int = 3) -> list[dict]:
    """
    Detect complaint spikes: clusters with threshold+ complaints
    arriving within window_hours. Returns list of spike dicts.
    """
    from datetime import datetime, timedelta
    db_path = db_path or get_db_path()
    if not os.path.exists(db_path):
        return []
    conn = sqlite3.connect(db_path)
    try:
        cutoff = (datetime.utcnow() -
                  timedelta(hours=window_hours)).isoformat()
        df = pd.read_sql_query(
            "SELECT * FROM complaints WHERE Complaint_Date >= ? AND Status != 'Resolved'",
            conn, params=(cutoff,))
    finally:
        conn.close()

    if df.empty:
        return []

    from src.resolution_playbooks import match_playbook
    spikes = []
    df["cluster_key"] = df["Issue"].fillna("").apply(match_playbook)
    for key, group in df.groupby("cluster_key"):
        if len(group) >= threshold:
            channels = group["Channel"].value_counts()
            spikes.append({
                "cluster_key": key,
                "count": len(group),
                "complaint_ids": group["Complaint_ID"].tolist(),
                "top_channel": channels.index[0] if not channels.empty else "Unknown",
                "keywords": key,
                "first_seen": group["Complaint_Date"].min(),
            })
    return sorted(spikes, key=lambda x: x["count"], reverse=True)
