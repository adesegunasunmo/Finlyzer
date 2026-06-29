"""
Module: auth.py
Purpose: Authentication — env-var mode (dev) + SQLite user accounts (production).
"""

import os
import json
import logging
from datetime import datetime
from typing import Literal, Optional

import streamlit as st

PASSWORD_ENV = "STREAMLIT_PASSWORD"
ADMIN_PASSWORD_ENV = "STREAMLIT_ADMIN_PASSWORD"
MAX_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOG_DIR = os.path.join(_BASE_DIR, "data")
os.makedirs(_LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(_LOG_DIR, "auth.log")

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")


def _log(success: bool, username: str):
    try:
        logging.info(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "success": success, "username": username
        }))
    except Exception:
        pass


def get_remaining_attempts() -> int:
    st.session_state.setdefault("login_attempts", 0)
    return MAX_ATTEMPTS - st.session_state.login_attempts


def require_auth() -> tuple[bool, Literal["admin", "viewer", None]]:
    if st.session_state.get("authenticated"):
        return True, st.session_state.get("role", "viewer")

    st.session_state.setdefault("login_attempts", 0)

    if st.session_state.login_attempts >= MAX_ATTEMPTS:
        st.error(
            f"Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.")
        return False, None

    # Read credentials — try DB users first, fall back to env vars
    admin_pw = ""
    viewer_pw = ""
    try:
        admin_pw = os.getenv(ADMIN_PASSWORD_ENV) or st.secrets.get(
            ADMIN_PASSWORD_ENV, "")
        viewer_pw = os.getenv(PASSWORD_ENV) or st.secrets.get(PASSWORD_ENV, "")
    except Exception:
        admin_pw = os.getenv(ADMIN_PASSWORD_ENV, "")
        viewer_pw = os.getenv(PASSWORD_ENV, "")

    st.markdown("### 🏦 Finlyzer — Secure Login")
    c1, c2 = st.columns([3, 1])
    with c1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input(
            "Password", type="password", key="login_password")
    with c2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        clicked = st.button("Login", use_container_width=True)

    # Also try DB-based login
    db_user = None
    if clicked and username and password:
        try:
            from src.db import verify_user, get_db_path
            db_path = get_db_path()
            if os.path.exists(db_path):
                db_user = verify_user(username, password, db_path)
        except Exception:
            pass

    if clicked:
        if not username:
            st.error("Username is required.")
            return False, None

        authenticated = False
        role = None

        if db_user:
            authenticated = True
            role = db_user.get("Role", "viewer")
        elif admin_pw and password == admin_pw:
            authenticated = True
            role = "admin"
        elif viewer_pw and password == viewer_pw:
            authenticated = True
            role = "viewer"

        if authenticated:
            st.session_state.authenticated = True
            st.session_state.role = role
            st.session_state.username = username
            st.session_state.login_attempts = 0
            _log(True, username)
            st.rerun()
        else:
            st.session_state.login_attempts += 1
            _log(False, username)
            remaining = get_remaining_attempts()
            st.error(f"Invalid credentials. {remaining} attempt(s) remaining.")

    if not (admin_pw or viewer_pw):
        st.info("No passwords configured — set STREAMLIT_PASSWORD / STREAMLIT_ADMIN_PASSWORD, "
                "or create users via the admin panel.")
        # Allow anonymous viewer access in dev
        if st.button("Continue as guest (viewer)"):
            st.session_state.authenticated = True
            st.session_state.role = "viewer"
            st.session_state.username = "guest"
            st.rerun()

    remaining = get_remaining_attempts()
    if remaining < MAX_ATTEMPTS:
        st.warning(f"{remaining} login attempt(s) remaining.")

    return False, None


def is_admin() -> bool:
    return st.session_state.get("role") == "admin"


def is_viewer() -> bool:
    return st.session_state.get("role") in ("admin", "viewer")
