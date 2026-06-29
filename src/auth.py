"""
Module: auth.py
Purpose: Authentication with role-based access (admin/viewer),
         login attempt limiting, and audit logging.
"""

import os
import json
import logging
from datetime import datetime
from typing import Literal, Optional

import streamlit as st

# Configuration
PASSWORD_ENV = "STREAMLIT_PASSWORD"
ADMIN_PASSWORD_ENV = "STREAMLIT_ADMIN_PASSWORD"
MAX_ATTEMPTS = 3
ATTEMPT_TIMEOUT_MINUTES = 15

# Absolute path so it works regardless of working directory or Streamlit Cloud CWD
_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_LOG_DIR = os.path.join(_BASE_DIR, "data")
os.makedirs(_LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(_LOG_DIR, "auth.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def check_password_strength(password: str) -> tuple[bool, str]:
    """Validate password meets minimum security requirements."""
    if len(password) < 8:
        return False, "Password must be at least 8 characters"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number"
    return True, "Password meets requirements"


def log_attempt(success: bool, username: str, ip: Optional[str] = None):
    """Log login attempts with timestamp and outcome."""
    msg = {
        "timestamp": datetime.now().isoformat(),
        "success": success,
        "username": username,
        "ip": ip or "unknown",
    }
    try:
        logging.info(json.dumps(msg))
    except Exception:
        pass  # Never crash the app over a logging failure


def get_remaining_attempts() -> int:
    """Return how many login attempts remain before lockout."""
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0
    return MAX_ATTEMPTS - st.session_state.login_attempts


def require_auth() -> tuple[bool, Literal["admin", "viewer", None]]:
    """
    Show login form or return current auth state.
    Returns (authenticated: bool, role: "admin" | "viewer" | None).
    """

    # Already authenticated — dashboard handles the logout button
    if st.session_state.get("authenticated"):
        role = st.session_state.get("role", "viewer")
        return True, role

    # Initialize attempt counter
    if "login_attempts" not in st.session_state:
        st.session_state.login_attempts = 0

    # Lockout check
    if st.session_state.login_attempts >= MAX_ATTEMPTS:
        st.error(
            f"Too many failed attempts. Please try again in {ATTEMPT_TIMEOUT_MINUTES} minutes."
        )
        return False, None

    # Read passwords from environment / Streamlit secrets
    try:
        admin_pw = os.getenv(ADMIN_PASSWORD_ENV) or st.secrets.get(
            ADMIN_PASSWORD_ENV, "")
        viewer_pw = os.getenv(PASSWORD_ENV) or st.secrets.get(PASSWORD_ENV, "")
    except Exception:
        admin_pw = os.getenv(ADMIN_PASSWORD_ENV, "")
        viewer_pw = os.getenv(PASSWORD_ENV, "")

    if not (admin_pw or viewer_pw):
        st.warning(
            "No passwords configured. Set STREAMLIT_PASSWORD and/or "
            "STREAMLIT_ADMIN_PASSWORD in your environment or Streamlit secrets."
        )
        # Default to viewer access so the app is still usable during development
        return True, "viewer"

    # Login form
    st.markdown("### 🏦 Finlyzer — Login")
    col1, col2 = st.columns([3, 1])

    with col1:
        username = st.text_input("Username", key="login_username")
        password = st.text_input(
            "Password", type="password", key="login_password")

    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        login_clicked = st.button("Login", use_container_width=True)

    if login_clicked:
        if not username:
            st.error("Username is required.")
            return False, None

        if admin_pw and password == admin_pw:
            st.session_state.authenticated = True
            st.session_state.role = "admin"
            st.session_state.username = username
            st.session_state.login_attempts = 0
            log_attempt(True, username)
            st.rerun()

        elif viewer_pw and password == viewer_pw:
            st.session_state.authenticated = True
            st.session_state.role = "viewer"
            st.session_state.username = username
            st.session_state.login_attempts = 0
            log_attempt(True, username)
            st.rerun()

        else:
            st.session_state.login_attempts += 1
            log_attempt(False, username)
            remaining = get_remaining_attempts()
            st.error(f"Invalid credentials. {remaining} attempt(s) remaining.")

    remaining = get_remaining_attempts()
    if remaining < MAX_ATTEMPTS:
        st.warning(f"{remaining} login attempt(s) remaining before lockout.")

    return False, None


def is_admin() -> bool:
    """True if the current user has the admin role."""
    return st.session_state.get("role") == "admin"


def is_viewer() -> bool:
    """True if the current user has at least viewer access (admin or viewer)."""
    return st.session_state.get("role") in ("admin", "viewer")
