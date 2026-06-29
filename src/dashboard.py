import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))

import io
import time
import logging
import json
import uuid
from src.auth import require_auth, is_admin, is_viewer
from src.db import (
    get_db_path, get_all_complaints, update_complaints_bulk,
    log_call, get_calls,
    send_chat_message, get_chat_messages, get_all_chat,
    write_audit, get_audit_log,
    get_all_users, create_user, deactivate_user, reactivate_user,
    change_password, export_complaints_csv, export_complaints_excel,
    assign_complaint, init_db,
    init_extra_tables,
    create_it_incident, get_it_incidents, resolve_it_incident,
    get_system_status, update_system_status,
    log_notification, get_notifications, detect_spikes,
)
from src.resolution_playbooks import (
    PLAYBOOKS, SYSTEM_COMPONENTS, match_playbook, get_playbook
)
from src.utils import atomic_write_csv, atomic_write_json
from src.clustering import cluster_texts
from src.preprocessing import preprocess_text
from src.data_input import load_data
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
import plotly.express as px
import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..")))


# ── Helpers ───────────────────────────────────────────────────────────────────


def log_audit(action, details):
    user = st.session_state.get("username", "unknown")
    role = st.session_state.get("role", "unknown")
    try:
        write_audit(user, role, action, json.dumps(details), db_path=DB_PATH)
    except Exception:
        pass


def status_badge(s):
    c = {"Resolved": ("#1B5E20", "#E8F5E9"), "Pending": ("#E65100", "#FFF3E0"),
         "Escalated": ("#B71C1C", "#FFEBEE")}.get(s, ("#37474F", "#ECEFF1"))
    return f'<span style="background:{c[1]};color:{c[0]};padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700">{s}</span>'


def sev_badge(s):
    c = {"Critical": ("#B71C1C", "#FFEBEE"), "High": ("#E65100", "#FFF3E0"),
         "Medium": ("#F57F17", "#FFFDE7"), "Low": ("#1B5E20", "#E8F5E9")}.get(s, ("#37474F", "#ECEFF1"))
    return f'<span style="background:{c[1]};color:{c[0]};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700">{s}</span>'


def sys_badge(s):
    c = {"Operational": ("#1B5E20", "#E8F5E9"), "Degraded": ("#E65100", "#FFF3E0"),
         "Down": ("#B71C1C", "#FFEBEE"), "Maintenance": ("#1565C0", "#E3F2FD")}.get(s, ("#37474F", "#ECEFF1"))
    return f'<span style="background:{c[1]};color:{c[0]};padding:2px 8px;border-radius:8px;font-size:11px;font-weight:700">{s}</span>'


def sla_status(complaint_date, sla_hours=48):
    if pd.isna(complaint_date):
        return "Unknown", "#888"
    deadline = pd.Timestamp(complaint_date) + timedelta(hours=float(sla_hours))
    now = pd.Timestamp(datetime.now())
    if now > deadline:
        return "BREACHED", "#C62828"
    elif now > deadline - timedelta(hours=4):
        return "AT RISK", "#F9A825"
    return "On track", "#2E7D32"


def card(title, content_html):
    return f'<div style="background:#fff;border:0.5px solid #DDE3EC;border-radius:12px;padding:16px 18px;margin-bottom:12px"><div style="font-size:11px;font-weight:700;color:#6B778C;text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px;padding-bottom:8px;border-bottom:0.5px solid #DDE3EC">{title}</div>{content_html}</div>'

# ── Page config ───────────────────────────────────────────────────────────────


st.set_page_config(page_title="Finlyzer", page_icon="🏦",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
:root{--navy:#0A2342;--blue:#1565C0;--teal:#00897B;--gold:#F9A825;
      --danger:#C62828;--light:#F8FAFD;--border:#DDE3EC;--text:#172B4D;--muted:#6B778C}
#MainMenu,footer,header{visibility:hidden}
.block-container{padding-top:1.2rem!important}
[data-testid="stSidebar"]{background:var(--navy)!important}
[data-testid="stSidebar"] *{color:#CBD5E0!important}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:#fff!important;font-size:11px!important;text-transform:uppercase;letter-spacing:1px}
[data-testid="stSidebar"] .stButton button{background:#1565C0!important;color:#fff!important;border:none!important;width:100%}
.stButton button{background:var(--blue)!important;color:#fff!important;border:none!important;border-radius:8px!important;font-weight:600!important}
.stTabs [data-baseweb="tab"]{font-size:12px;font-weight:600;color:var(--muted)!important;padding:6px 14px}
.stTabs [aria-selected="true"]{color:var(--blue)!important;border-bottom:2px solid var(--blue)!important}
.ph{background:var(--navy);background:linear-gradient(135deg,var(--navy) 0%,#1565C0 100%);border-radius:14px;padding:20px 28px;margin-bottom:18px;color:#fff;display:flex;align-items:center;gap:14px}
.ph h1{font-size:21px;font-weight:700;margin:0;color:#fff!important}
.ph p{font-size:12px;color:#90CAF9;margin:2px 0 0}
.kc{background:#fff;border:1px solid var(--border);border-radius:12px;padding:16px 20px;position:relative;overflow:hidden}
.kc::before{content:"";position:absolute;top:0;left:0;width:4px;height:100%;background:var(--acc,var(--blue))}
.kl{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
.kv{font-size:26px;font-weight:700;line-height:1}
.ks{font-size:11px;color:var(--muted);margin-top:4px}
.chat-me{background:#E3F2FD;border-radius:12px 12px 4px 12px;padding:10px 14px;margin:5px 0;max-width:80%;margin-left:auto;font-size:13px}
.chat-other{background:#F1F8E9;border-radius:12px 12px 12px 4px;padding:10px 14px;margin:5px 0;max-width:80%;font-size:13px}
.chat-meta{font-size:10px;color:#888;margin-top:3px}
.step-li{display:flex;gap:10px;margin-bottom:8px;align-items:flex-start}
.step-dot{min-width:20px;height:20px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;flex-shrink:0;margin-top:1px}
.sla-breach{background:#FFEBEE;border:1px solid #EF9A9A;border-radius:8px;padding:8px 12px;margin:3px 0;font-size:12px}
.sla-risk{background:#FFFDE7;border:1px solid #FFF176;border-radius:8px;padding:8px 12px;margin:3px 0;font-size:12px}
.sys-ok{background:#E8F5E9;border-radius:8px;padding:6px 10px;margin:3px 0;font-size:12px;display:flex;justify-content:space-between}
.sys-bad{background:#FFEBEE;border-radius:8px;padding:6px 10px;margin:3px 0;font-size:12px;display:flex;justify-content:space-between}
.sys-warn{background:#FFF3E0;border-radius:8px;padding:6px 10px;margin:3px 0;font-size:12px;display:flex;justify-content:space-between}
.spike-card{background:#FFF3E0;border:1px solid #FFCC02;border-radius:10px;padding:12px 14px;margin:6px 0}
.playbook-step{background:#F8FAFD;border-left:3px solid #1565C0;border-radius:0 8px 8px 0;padding:8px 12px;margin:4px 0;font-size:13px}
.it-step{background:#F3E5F5;border-left:3px solid #7B1FA2;border-radius:0 8px 8px 0;padding:8px 12px;margin:4px 0;font-size:13px}
.cust-msg{background:#E8F5E9;border:1px solid #A5D6A7;border-radius:8px;padding:10px 14px;font-size:13px;font-style:italic}
.role-badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;text-transform:uppercase}
.role-admin{background:#E8F5E9;color:#1B5E20}
.role-viewer{background:#E3F2FD;color:#0C447C}
</style>""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────

st.sidebar.markdown("""<div style="text-align:center;padding:16px 0 20px">
  <div style="font-size:32px">🏦</div>
  <div style="color:#fff;font-size:16px;font-weight:700;letter-spacing:1px">FINLYZER</div>
  <div style="color:#90A4AE;font-size:10px;margin-top:2px">Banking Intelligence Platform</div>
</div>""", unsafe_allow_html=True)

authenticated, role = require_auth()
if not authenticated:
    st.stop()

username = st.session_state.get("username", "User")
role_label = st.session_state.get("role", "viewer")
role_cls = "role-admin" if role_label == "admin" else "role-viewer"

st.sidebar.markdown(
    f'<div style="text-align:center;padding-bottom:12px">'
    f'<span class="role-badge {role_cls}">{role_label}</span>'
    f'<div style="color:#CBD5E0;font-size:11px;margin-top:4px">👤 {username}</div></div>',
    unsafe_allow_html=True)

if st.sidebar.button("🚪 Logout"):
    for k in ["authenticated", "role", "username", "login_attempts"]:
        st.session_state.pop(k, None)
    st.rerun()

st.sidebar.markdown(
    "<hr style='border-color:#1E3A5F;margin:6px 0 12px'>", unsafe_allow_html=True)

# ── Paths & init ──────────────────────────────────────────────────────────────

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE, "data", "failed_transactions.csv")
DB_PATH = get_db_path()
THEME = "plotly_white"
PALETTE = px.colors.qualitative.Bold

if not os.path.exists(DB_PATH):
    init_db(db_path=DB_PATH, csv_path=DATA_PATH)
init_extra_tables(DB_PATH)

# seed system status defaults
try:
    existing_status = get_system_status(DB_PATH)
    if existing_status.empty:
        for sc in SYSTEM_COMPONENTS:
            update_system_status(sc["id"], sc["name"], "Operational", "",
                                 "system", DB_PATH)
except Exception:
    pass

df = None
try:
    df = get_all_complaints(DB_PATH)
except Exception as e:
    st.error(f"DB error: {e}")

if df is None or df.empty:
    try:
        df = load_data(DATA_PATH)
        init_db(db_path=DB_PATH, csv_path=DATA_PATH)
        df = get_all_complaints(DB_PATH)
    except Exception as e:
        st.error(f"Data error: {e}")
        df = None

if df is not None and not df.empty:
    for col in ("Transaction_Date", "Complaint_Date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    for col in ("Customer_Email", "Phone", "Assigned_Agent"):
        if col not in df.columns:
            df[col] = ""
    if "SLA_Hours" not in df.columns:
        df["SLA_Hours"] = 48

try:
    calls_df = get_calls(DB_PATH) if os.path.exists(
        DB_PATH) else pd.DataFrame()
except Exception:
    calls_df = pd.DataFrame()

if df is None or df.empty:
    st.markdown('<div class="ph"><div style="font-size:38px">🏦</div><div><h1>Finlyzer</h1><p>No data found. Place failed_transactions.csv in data/ and restart.</p></div></div>', unsafe_allow_html=True)
    st.stop()

# ── Sidebar filters ───────────────────────────────────────────────────────────

st.sidebar.markdown("### 🔍 Filters")
min_date = df["Complaint_Date"].min().date()
max_date = df["Complaint_Date"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date))
all_ch = sorted(df["Channel"].dropna().unique())
channels = st.sidebar.multiselect("Channel", all_ch, default=all_ch)
all_st = sorted(df["Status"].dropna().unique())
statuses = st.sidebar.multiselect("Status", all_st, default=all_st)
search = st.sidebar.text_input("🔎 Search", placeholder="ATM, loan, fraud…")

st.sidebar.markdown(
    "<hr style='border-color:#1E3A5F;margin:10px 0'>", unsafe_allow_html=True)
st.sidebar.markdown("### ⚙️ AI")
cluster_n = st.sidebar.slider("Clusters", 2, 10, 5)
max_features = st.sidebar.slider("TF-IDF features", 500, 5000, 2000, step=500)
spike_window = st.sidebar.slider("Spike window (hours)", 1, 24, 2)
spike_thresh = st.sidebar.slider("Spike threshold", 2, 10, 3)

# ── Apply filters ─────────────────────────────────────────────────────────────

s_d, e_d = date_range if len(date_range) == 2 else (min_date, max_date)
mask = df["Complaint_Date"].dt.date.between(s_d, e_d)
mask &= df["Channel"].isin(channels)
mask &= df["Status"].isin(statuses)
if search:
    mask &= df["Issue"].str.contains(search, case=False, na=False)
filtered = df.loc[mask].copy()

# ── SLA alerts sidebar ────────────────────────────────────────────────────────

breached = [r["Complaint_ID"] for _, r in filtered[filtered["Status"] != "Resolved"].iterrows()
            if sla_status(r.get("Complaint_Date"), r.get("SLA_Hours", 48))[0] == "BREACHED"]
at_risk = [r["Complaint_ID"] for _, r in filtered[filtered["Status"] != "Resolved"].iterrows()
           if sla_status(r.get("Complaint_Date"), r.get("SLA_Hours", 48))[0] == "AT RISK"]
if breached:
    st.sidebar.markdown(
        f'<div class="sla-breach">🚨 <b>{len(breached)}</b> SLA breach(es)</div>', unsafe_allow_html=True)
if at_risk:
    st.sidebar.markdown(
        f'<div class="sla-risk">⚠️ <b>{len(at_risk)}</b> at risk</div>', unsafe_allow_html=True)

# ── System status sidebar ─────────────────────────────────────────────────────

try:
    sys_status_df = get_system_status(DB_PATH)
    issues = sys_status_df[sys_status_df["Status"] !=
                           "Operational"] if not sys_status_df.empty else pd.DataFrame()
    if not issues.empty:
        st.sidebar.markdown(
            "<hr style='border-color:#1E3A5F;margin:6px 0'>", unsafe_allow_html=True)
        st.sidebar.markdown("### 🔴 Active outages")
        for _, row in issues.iterrows():
            col = "#C62828" if row["Status"] == "Down" else "#F9A825"
            st.sidebar.markdown(
                f'<div style="background:#1E3A5F;border-left:3px solid {col};border-radius:4px;padding:5px 8px;margin:3px 0;font-size:11px;color:#CBD5E0">'
                f'{row["Component_Name"]}: <b style="color:{col}">{row["Status"]}</b></div>',
                unsafe_allow_html=True)
except Exception:
    pass

# ── Page header ───────────────────────────────────────────────────────────────

total = len(filtered)
resolved = int((filtered["Status"] == "Resolved").sum())
pending = int((filtered["Status"] == "Pending").sum())
escalated = int((filtered["Status"] == "Escalated").sum())
res_rate = f"{resolved/total*100:.1f}%" if total else "0%"
avg_res = pd.to_numeric(filtered.get(
    "Resolution_Time", pd.Series(dtype=float)), errors="coerce").dropna()
avg_str = f"{avg_res.mean():.1f}d" if not avg_res.empty else "—"

st.markdown(f"""<div class="ph">
  <div style="font-size:40px">🏦</div>
  <div><h1>Finlyzer — Banking Intelligence</h1>
  <p>AI complaint management · {total:,} complaints · {datetime.now().strftime("%d %b %Y %H:%M")}</p></div>
</div>""", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
for col, lbl, val, sub, acc in [
    (k1, "Total", f"{total:,}", f"{s_d}→{e_d}", "#1565C0"),
    (k2, "Resolved", f"{resolved:,}", f"Rate: {res_rate}", "#00897B"),
    (k3, "Pending", f"{pending:,}", "Awaiting action", "#F9A825"),
    (k4, "Escalated", f"{escalated:,}", "Needs attention", "#C62828"),
    (k5, "Avg Resolution", avg_str, "Days to close", "#5C35CC"),
]:
    col.markdown(
        f'<div class="kc" style="--acc:{acc}"><div class="kl">{lbl}</div><div class="kv" style="color:{acc}">{val}</div><div class="ks">{sub}</div></div>', unsafe_allow_html=True)

st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════

tabs = st.tabs([
    "📊 Analytics", "🧑‍💼 Agent Workspace", "🖥️ IT Command",
    "💬 Team Chat", "🤖 AI Clustering", "📤 Export",
    "👥 Users", "🔐 My Account", "📋 Audit"
])
(tab_analytics, tab_agent, tab_it, tab_chat,
 tab_cluster, tab_export, tab_users, tab_account, tab_audit) = tabs

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
with tab_analytics:
    r1, r2 = st.columns([3, 2])
    with r1:
        ts = filtered.groupby(filtered["Complaint_Date"].dt.to_period(
            "W").dt.start_time).size().reset_index(name="count")
        fig = px.area(ts, x="Complaint_Date", y="count",
                      color_discrete_sequence=["#1565C0"])
        fig.update_traces(
            fill="tozeroy", fillcolor="rgba(21,101,192,0.08)", line_width=2)
        fig.update_layout(template=THEME, margin=dict(l=0, r=0, t=8, b=0), height=220,
                          plot_bgcolor="#fff", paper_bgcolor="#fff",
                          font=dict(family="Inter,sans-serif", size=12),
                          xaxis_title="", yaxis_title="Complaints")
        st.subheader("Complaints over time")
        st.plotly_chart(fig, use_container_width=True)
    with r2:
        chan = filtered["Channel"].value_counts().reset_index()
        chan.columns = ["Channel", "Count"]
        fig2 = px.pie(chan, names="Channel", values="Count",
                      color_discrete_sequence=PALETTE, hole=0.52)
        fig2.update_layout(template=THEME, margin=dict(l=0, r=0, t=8, b=0), height=220,
                           plot_bgcolor="#fff", paper_bgcolor="#fff",
                           font=dict(family="Inter,sans-serif", size=12))
        st.subheader("By channel")
        st.plotly_chart(fig2, use_container_width=True)

    r3, r4 = st.columns([2, 3])
    with r3:
        sc = filtered["Status"].value_counts().reset_index()
        sc.columns = ["Status", "Count"]
        fig3 = px.bar(sc, x="Status", y="Count", color="Status",
                      color_discrete_map={"Resolved": "#00897B", "Pending": "#F9A825", "Escalated": "#C62828"}, text="Count")
        fig3.update_layout(template=THEME, margin=dict(l=0, r=0, t=8, b=0), height=240,
                           showlegend=False, plot_bgcolor="#fff", paper_bgcolor="#fff",
                           font=dict(family="Inter,sans-serif", size=12))
        fig3.update_traces(textposition="outside", marker_line_width=0)
        st.subheader("Status breakdown")
        st.plotly_chart(fig3, use_container_width=True)
    with r4:
        top = filtered["Issue"].value_counts().nlargest(8).reset_index()
        top.columns = ["Issue", "Count"]
        top["Issue"] = top["Issue"].str[:55]
        fig4 = px.bar(top, x="Count", y="Issue", orientation="h",
                      color="Count", color_continuous_scale=["#90CAF9", "#1565C0"], text="Count")
        fig4.update_layout(template=THEME, margin=dict(l=0, r=0, t=8, b=0),
                           yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                           plot_bgcolor="#fff", paper_bgcolor="#fff",
                           font=dict(family="Inter,sans-serif", size=11), height=240)
        fig4.update_traces(textposition="outside", marker_line_width=0)
        st.subheader("Top complaint issues")
        st.plotly_chart(fig4, use_container_width=True)

    heat = filtered.groupby(["Channel", "Status"]
                            ).size().reset_index(name="Count")
    if not heat.empty:
        hp = heat.pivot(index="Channel", columns="Status",
                        values="Count").fillna(0)
        fig5 = px.imshow(hp, color_continuous_scale=[
                         "#EFF6FF", "#1565C0"], text_auto=True, aspect="auto")
        fig5.update_layout(template=THEME, margin=dict(l=0, r=0, t=8, b=0), height=180,
                           plot_bgcolor="#fff", paper_bgcolor="#fff",
                           font=dict(family="Inter,sans-serif", size=12), coloraxis_showscale=False)
        st.subheader("Channel × Status heatmap")
        st.plotly_chart(fig5, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — AGENT WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
with tab_agent:
    st.markdown(
        "#### 🧑‍💼 Agent workspace — customer lookup and live resolution guide")

    # System status banner for agents
    try:
        sys_df = get_system_status(DB_PATH)
        outages = sys_df[sys_df["Status"] !=
                         "Operational"] if not sys_df.empty else pd.DataFrame()
        if not outages.empty:
            for _, row in outages.iterrows():
                col = "#C62828" if row["Status"] == "Down" else "#E65100"
                st.markdown(
                    f'<div style="background:{col};color:#fff;padding:10px 16px;border-radius:8px;margin-bottom:8px;font-size:13px">'
                    f'🔴 <b>KNOWN ISSUE:</b> {row["Component_Name"]} is <b>{row["Status"]}</b>. '
                    f'{row["Message"]} — Tell customers: "We are aware and working on it."</div>',
                    unsafe_allow_html=True)
    except Exception:
        pass

    # Search bar
    st.markdown("##### Search customer")
    sc1, sc2 = st.columns([4, 1])
    cust_search = sc1.text_input("Search by customer ID, phone, email or complaint ID",
                                 placeholder="e.g. CUST001 or 08012345678 or C001",
                                 label_visibility="collapsed")
    search_clicked = sc2.button("🔍 Search", use_container_width=True)

    if cust_search or search_clicked:
        q = cust_search.strip().upper()
        hits = df[
            df["Customer_ID"].str.upper().str.contains(q, na=False) |
            df["Complaint_ID"].str.upper().str.contains(q, na=False) |
            df["Customer_Email"].str.upper().str.contains(q, na=False) |
            df["Phone"].str.contains(cust_search.strip(), na=False)
        ]

        if hits.empty:
            st.warning(
                "No complaints found for that search. Check the customer ID or phone number.")
        else:
            ac1, ac2 = st.columns([1, 2])

            with ac1:
                st.markdown("**Customer profile**")
                cust_id = hits["Customer_ID"].iloc[0]
                open_count = len(hits[hits["Status"] != "Resolved"])
                total_count = len(hits)
                escalated_count = len(hits[hits["Status"] == "Escalated"])
                risk = "🔴 HIGH" if escalated_count > 2 else (
                    "🟡 MEDIUM" if open_count > 1 else "🟢 NORMAL")

                st.markdown(f"""
                <div style="background:#fff;border:0.5px solid #DDE3EC;border-radius:12px;padding:14px">
                  <div style="font-size:32px;text-align:center;margin-bottom:8px">👤</div>
                  <table style="width:100%;font-size:12px">
                    <tr><td style="color:#6B778C">Customer ID</td><td style="font-weight:600;text-align:right">{cust_id}</td></tr>
                    <tr><td style="color:#6B778C">Total complaints</td><td style="font-weight:600;text-align:right">{total_count}</td></tr>
                    <tr><td style="color:#6B778C">Open</td><td style="font-weight:600;text-align:right;color:#E65100">{open_count}</td></tr>
                    <tr><td style="color:#6B778C">Escalated</td><td style="font-weight:600;text-align:right;color:#C62828">{escalated_count}</td></tr>
                    <tr><td style="color:#6B778C">Risk level</td><td style="font-weight:600;text-align:right">{risk}</td></tr>
                    <tr><td style="color:#6B778C">Email</td><td style="font-weight:600;text-align:right;font-size:11px">{hits["Customer_Email"].iloc[0] or "—"}</td></tr>
                    <tr><td style="color:#6B778C">Phone</td><td style="font-weight:600;text-align:right">{hits["Phone"].iloc[0] or "—"}</td></tr>
                  </table>
                </div>""", unsafe_allow_html=True)

                st.markdown("<div style='height:10px'></div>",
                            unsafe_allow_html=True)
                st.markdown("**Complaint history**")
                for _, row in hits.sort_values("Complaint_Date", ascending=False).head(5).iterrows():
                    slbl, scol = sla_status(
                        row.get("Complaint_Date"), row.get("SLA_Hours", 48))
                    st.markdown(
                        f'<div style="background:#F8FAFD;border-left:3px solid #1565C0;border-radius:0 8px 8px 0;padding:8px 10px;margin:4px 0;font-size:12px">'
                        f'<b>{row["Complaint_ID"]}</b> · {str(row.get("Complaint_Date",""))[:10]}<br>'
                        f'{row["Issue"][:60]}{"…" if len(str(row["Issue"]))>60 else ""}<br>'
                        f'{status_badge(row["Status"])} <span style="color:{scol};font-size:11px;font-weight:600">SLA: {slbl}</span></div>',
                        unsafe_allow_html=True)

            with ac2:
                # Select active complaint
                open_complaints = hits[hits["Status"] != "Resolved"]
                all_complaints = hits
                complaint_opts = all_complaints["Complaint_ID"].tolist()

                sel = st.selectbox(
                    "Select complaint to work on", complaint_opts)
                comp = hits[hits["Complaint_ID"] == sel].iloc[0]

                # AI resolution playbook
                pb_key = match_playbook(str(comp.get("Issue", "")))
                pb = get_playbook(pb_key)

                st.markdown(f"""
                <div style="background:#E8F5E9;border:1px solid #A5D6A7;border-radius:10px;padding:12px 14px;margin-bottom:10px">
                  <div style="font-size:13px;font-weight:700;color:#1B5E20">
                    {pb['icon']} AI matched: <b>{pb['title']}</b>
                    &nbsp;&nbsp;<span style="font-size:11px;font-weight:400;color:#2E7D32">SLA: {pb['sla_hours']}h</span>
                  </div>
                </div>""", unsafe_allow_html=True)

                st.markdown("**Resolution steps for agent**")
                for i, step in enumerate(pb["agent_steps"], 1):
                    clr = "#C62828" if i == 1 and pb_key == "FRAUD" else "#1565C0"
                    st.markdown(
                        f'<div class="playbook-step"><span style="color:{clr};font-weight:700;margin-right:8px">{i}.</span>{step}</div>',
                        unsafe_allow_html=True)

                st.markdown("**Customer message template**")
                ref = comp["Complaint_ID"]
                msg = pb["customer_message"].format(ref=ref)
                st.markdown(
                    f'<div class="cust-msg">"{msg}"</div>', unsafe_allow_html=True)
                if st.button("📋 Copy message / Log notification"):
                    log_notification(
                        ref, comp["Customer_ID"], "Agent", msg, DB_PATH)
                    log_audit("notification_sent", {"complaint_id": ref})
                    st.success("Notification logged.")

                st.markdown("<hr>", unsafe_allow_html=True)

                # Quick action buttons
                qa1, qa2, qa3 = st.columns(3)
                with qa1:
                    if st.button("✅ Mark Resolved", use_container_width=True):
                        df.loc[df["Complaint_ID"] ==
                               sel, "Status"] = "Resolved"
                        update_complaints_bulk(
                            df[df["Complaint_ID"] == sel], DB_PATH)
                        log_audit("resolve_complaint", {"id": sel})
                        st.success("Marked resolved.")
                        st.rerun()
                with qa2:
                    if st.button("🚨 Escalate to IT", use_container_width=True, type="primary"):
                        inc_id = create_it_incident(
                            title=f"{pb['title']} — {comp['Channel']}",
                            description=str(comp.get("Issue", "")),
                            cluster_key=pb_key,
                            affected_channel=str(comp.get("Channel", "")),
                            complaint_ids=[sel],
                            severity="High" if pb_key == "FRAUD" else "Medium",
                            created_by=username,
                            db_path=DB_PATH,
                        )
                        df.loc[df["Complaint_ID"] ==
                               sel, "Status"] = "Escalated"
                        update_complaints_bulk(
                            df[df["Complaint_ID"] == sel], DB_PATH)
                        log_audit("escalate_to_it", {
                                  "id": sel, "incident": inc_id})
                        st.error(f"Escalated to IT. Incident: {inc_id}")
                with qa3:
                    if st.button("📞 Log call", use_container_width=True):
                        st.session_state["log_call_complaint"] = sel

                # Call log form
                if st.session_state.get("log_call_complaint") == sel:
                    with st.form("agent_call_form"):
                        out = st.selectbox("Outcome", [
                                           "Answered", "No answer", "Voicemail", "Callback requested", "Escalated"])
                        notes = st.text_area("Notes", height=60)
                        if st.form_submit_button("Save call"):
                            log_call({"Call_ID": str(uuid.uuid4()), "Complaint_ID": sel,
                                      "Customer_ID": comp["Customer_ID"], "Call_Date": datetime.utcnow().isoformat(),
                                      "Agent": username, "Outcome": out, "Notes": notes,
                                      "Escalated": out == "Escalated", "Follow_Up_Date": ""}, DB_PATH)
                            log_audit(
                                "log_call", {"complaint_id": sel, "outcome": out})
                            st.success("Call logged.")
                            st.session_state.pop("log_call_complaint", None)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — IT COMMAND
# ══════════════════════════════════════════════════════════════════════════════
with tab_it:
    st.markdown(
        "#### 🖥️ IT command centre — incident management and system status")

    # Spike detection
    st.markdown("##### AI spike detection")
    if st.button("🔍 Scan for complaint spikes now"):
        with st.spinner("Scanning complaint patterns…"):
            spikes = detect_spikes(DB_PATH, spike_window, spike_thresh)
        st.session_state["spikes"] = spikes

    if "spikes" in st.session_state:
        spikes = st.session_state["spikes"]
        if not spikes:
            st.success(
                f"No spikes detected in the last {spike_window} hours. All clear.")
        else:
            st.warning(f"⚠️ {len(spikes)} spike(s) detected")
            for sp in spikes:
                pb = get_playbook(sp["cluster_key"])
                with st.expander(f"🔴 {pb['icon']} {pb['title']} — {sp['count']} complaints — Channel: {sp['top_channel']}", expanded=True):
                    sc1, sc2 = st.columns([3, 1])
                    with sc1:
                        st.markdown(
                            f"**Complaints in spike:** {', '.join(sp['complaint_ids'][:5])}{'…' if len(sp['complaint_ids'])>5 else ''}")
                        st.markdown(f"**IT resolution steps:**")
                        for i, step in enumerate(pb["it_steps"], 1):
                            st.markdown(
                                f'<div class="it-step">{i}. {step}</div>', unsafe_allow_html=True)
                    with sc2:
                        sev = "Critical" if sp["count"] >= 8 else (
                            "High" if sp["count"] >= 5 else "Medium")
                        if st.button(f"🚨 Raise IT incident", key=f"raise_{sp['cluster_key']}"):
                            inc_id = create_it_incident(
                                title=f"SPIKE: {pb['title']}",
                                description=f"{sp['count']} complaints in {spike_window}h window",
                                cluster_key=sp["cluster_key"],
                                affected_channel=sp["top_channel"],
                                complaint_ids=sp["complaint_ids"],
                                severity=sev,
                                created_by=username,
                                db_path=DB_PATH,
                            )
                            log_audit("raise_it_incident", {
                                      "spike_key": sp["cluster_key"], "incident": inc_id})
                            st.success(f"Incident {inc_id} raised.")
                            st.rerun()

    st.markdown("---")

    # Active incidents
    st.markdown("##### Active IT incidents")
    try:
        incidents = get_it_incidents(DB_PATH, status="Open")
    except Exception:
        incidents = pd.DataFrame()

    if incidents.empty:
        st.info("No open incidents.")
    else:
        for _, inc in incidents.iterrows():
            pb = get_playbook(inc.get("Cluster_Key", "ATM"))
            with st.expander(f"{sev_badge(inc['Severity'])} {pb['icon']} {inc['Title']} — {inc['Created_At'][:16]}", expanded=False):
                ic1, ic2 = st.columns([3, 1])
                with ic1:
                    st.markdown(f"**Incident ID:** `{inc['Incident_ID']}`")
                    st.markdown(f"**Channel:** {inc['Affected_Channel']}")
                    st.markdown(f"**Description:** {inc['Description']}")
                    st.markdown(f"**Complaints:** {inc['Complaint_IDs']}")
                    st.markdown("**IT steps:**")
                    for i, step in enumerate(pb["it_steps"], 1):
                        st.markdown(
                            f'<div class="it-step">{i}. {step}</div>', unsafe_allow_html=True)
                with ic2:
                    if st.button("Declare system outage", key=f"outage_{inc['Incident_ID']}"):
                        comp_map = {"ATM": "atm_network", "MOBILE": "mobile_banking",
                                    "USSD": "ussd", "POS": "pos_network", "TRANSFER": "nip_nibss"}
                        comp_id = comp_map.get(
                            inc.get("Cluster_Key", ""), "atm_network")
                        comp_name = next(
                            (s["name"] for s in SYSTEM_COMPONENTS if s["id"] == comp_id), comp_id)
                        update_system_status(comp_id, comp_name, "Down",
                                             f"Incident {inc['Incident_ID']} — under investigation", username, DB_PATH)
                        log_audit("declare_outage", {
                                  "incident": inc["Incident_ID"], "component": comp_id})
                        st.warning("Outage declared. All agents notified.")
                        st.rerun()

                    res_note = st.text_area(
                        "Resolution note", key=f"rn_{inc['Incident_ID']}", height=80)
                    if st.button("✅ Resolve + bulk close complaints", key=f"res_{inc['Incident_ID']}"):
                        resolve_it_incident(
                            inc["Incident_ID"], username, res_note, DB_PATH)
                        # Bulk close all complaints in this incident
                        cids = [c.strip() for c in str(
                            inc["Complaint_IDs"]).split(",") if c.strip()]
                        if cids:
                            df.loc[df["Complaint_ID"].isin(
                                cids), "Status"] = "Resolved"
                            update_complaints_bulk(
                                df[df["Complaint_ID"].isin(cids)], DB_PATH)
                        # Clear system status
                        comp_map = {"ATM": "atm_network", "MOBILE": "mobile_banking",
                                    "USSD": "ussd", "POS": "pos_network", "TRANSFER": "nip_nibss"}
                        comp_id = comp_map.get(
                            inc.get("Cluster_Key", ""), "atm_network")
                        comp_name = next(
                            (s["name"] for s in SYSTEM_COMPONENTS if s["id"] == comp_id), comp_id)
                        update_system_status(
                            comp_id, comp_name, "Operational", "", username, DB_PATH)
                        log_audit("resolve_incident", {
                                  "incident": inc["Incident_ID"], "closed": len(cids)})
                        st.success(
                            f"Incident resolved. {len(cids)} complaint(s) closed.")
                        st.rerun()

    st.markdown("---")

    # System status board
    st.markdown("##### System status board")
    st.markdown('<p style="font-size:13px;color:#6B778C;margin-bottom:10px">Update component status so agents see outages in real time.</p>', unsafe_allow_html=True)
    try:
        sys_df = get_system_status(DB_PATH)
    except Exception:
        sys_df = pd.DataFrame()

    if not sys_df.empty:
        for _, row in sys_df.iterrows():
            scol = {"Operational": "#2E7D32", "Degraded": "#E65100",
                    "Down": "#C62828", "Maintenance": "#1565C0"}.get(row["Status"], "#555")
            sc1, sc2, sc3, sc4 = st.columns([2, 1, 3, 1])
            sc1.markdown(f"**{row['Component_Name']}**")
            sc2.markdown(
                f'<span style="color:{scol};font-weight:700;font-size:13px">{row["Status"]}</span>', unsafe_allow_html=True)
            new_msg = sc3.text_input("Message", value=row.get(
                "Message", ""), label_visibility="collapsed", key=f"msg_{row['Component_ID']}")
            new_st = sc4.selectbox("", ["Operational", "Degraded", "Down", "Maintenance"],
                                   index=["Operational", "Degraded", "Down", "Maintenance"].index(
                                       row["Status"]) if row["Status"] in ["Operational", "Degraded", "Down", "Maintenance"] else 0,
                                   label_visibility="collapsed", key=f"st_{row['Component_ID']}")
            if sc4.button("Update", key=f"upd_{row['Component_ID']}"):
                update_system_status(
                    row["Component_ID"], row["Component_Name"], new_st, new_msg, username, DB_PATH)
                log_audit("update_system_status", {
                          "component": row["Component_ID"], "status": new_st})
                st.success(f"{row['Component_Name']} updated.")
                st.rerun()

    # Resolved incidents
    with st.expander("View resolved incidents"):
        try:
            resolved_inc = get_it_incidents(DB_PATH, status="Resolved")
            if not resolved_inc.empty:
                st.dataframe(resolved_inc[["Incident_ID", "Title", "Severity", "Created_At", "Resolved_At", "Resolution_Note"]],
                             use_container_width=True, height=200)
        except Exception:
            st.info("No resolved incidents yet.")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — TEAM CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.markdown("#### 💬 Internal team chat — collaborate per complaint")
    if not filtered.empty:
        chat_complaint = st.selectbox(
            "Complaint to discuss", filtered["Complaint_ID"].tolist(), key="chat_sel")
        try:
            msgs = get_chat_messages(chat_complaint, DB_PATH)
        except Exception:
            msgs = pd.DataFrame()

        if msgs.empty:
            st.markdown(
                '<p style="color:#6B778C;font-size:13px;text-align:center;padding:20px">No messages yet.</p>', unsafe_allow_html=True)
        else:
            for _, m in msgs.iterrows():
                is_me = m["Sender"] == username
                cls = "chat-me" if is_me else "chat-other"
                ts = str(m.get("Timestamp", ""))[:16].replace("T", " ")
                st.markdown(
                    f'<div style="text-align:{"right" if is_me else "left"}">'
                    f'<div class="{cls}">{m["Message"]}'
                    f'<div class="chat-meta">{m["Sender"]} · {m["Role"]} · {ts}</div></div></div>',
                    unsafe_allow_html=True)

        with st.form("chat_form", clear_on_submit=True):
            cc1, cc2 = st.columns([5, 1])
            msg_text = cc1.text_input("Message…", label_visibility="collapsed")
            if cc2.form_submit_button("Send"):
                if msg_text.strip():
                    send_chat_message(chat_complaint, username,
                                      role_label, msg_text.strip(), DB_PATH)
                    st.rerun()

        with st.expander("All recent team messages"):
            try:
                all_m = get_all_chat(DB_PATH)
                if not all_m.empty:
                    st.dataframe(all_m[["Complaint_ID", "Sender", "Role", "Message", "Timestamp"]],
                                 use_container_width=True, height=200)
            except Exception:
                pass

# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — AI CLUSTERING
# ══════════════════════════════════════════════════════════════════════════════
with tab_cluster:
    st.markdown("#### 🤖 AI clustering — surface root causes")
    st.markdown('<p style="font-size:13px;color:#6B778C;margin-bottom:12px">Groups complaints by similarity using TF-IDF + K-Means. Use this to spot systemic issues before they become crises.</p>', unsafe_allow_html=True)
    if st.button("🚀 Run clustering"):
        with st.spinner("Analysing…"):
            texts = filtered["Issue"].fillna(
                "").apply(preprocess_text).tolist()
            if len(texts) >= 2:
                vec = TfidfVectorizer(
                    max_features=max_features, stop_words="english")
                X = vec.fit_transform(texts)
                labels = cluster_texts(
                    texts, n_clusters=min(cluster_n, len(texts)))
                svd = TruncatedSVD(n_components=2, random_state=42)
                coords = svd.fit_transform(X)
                pdf = filtered.reset_index(drop=True).copy()
                pdf["Cluster"] = [f"Cluster {l+1}" for l in labels]
                pdf["Playbook"] = pdf["Issue"].fillna("").apply(
                    lambda t: get_playbook(match_playbook(t))["title"])
                pdf["x"] = coords[:, 0]
                pdf["y"] = coords[:, 1]
                st.session_state["clustered_df"] = pdf
                summary = pdf.groupby(["Cluster", "Playbook"]).agg(
                    Count=("Complaint_ID", "count"),
                    Resolved=("Status", lambda s: (s == "Resolved").sum()),
                    Escalated=("Status", lambda s: (s == "Escalated").sum()),
                ).reset_index()
                summary["Resolution %"] = (
                    summary["Resolved"]/summary["Count"]*100).round(1).astype(str)+"%"
                st.dataframe(summary, use_container_width=True, height=200)

    if "clustered_df" in st.session_state:
        pdf = st.session_state["clustered_df"]
        fig_s = px.scatter(pdf, x="x", y="y", color="Cluster",
                           color_discrete_sequence=PALETTE,
                           hover_data=["Complaint_ID", "Issue",
                                       "Channel", "Status", "Playbook"],
                           title="Complaint clusters", height=440)
        fig_s.update_traces(marker=dict(
            size=9, opacity=0.85, line=dict(width=0.5, color="#fff")))
        fig_s.update_layout(template=THEME, plot_bgcolor="#F8FAFD", paper_bgcolor="#fff",
                            font=dict(family="Inter,sans-serif", size=12),
                            margin=dict(l=0, r=0, t=36, b=0),
                            legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig_s, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — EXPORT
# ══════════════════════════════════════════════════════════════════════════════
with tab_export:
    st.markdown("#### 📤 Export data")
    e1, e2, e3 = st.columns(3)
    with e1:
        st.markdown("**CSV**")
        st.download_button("⬇️ Complaints CSV",
                           data=export_complaints_csv(filtered),
                           file_name=f"finlyzer_{datetime.now().strftime('%Y%m%d')}.csv",
                           mime="text/csv", use_container_width=True)
    with e2:
        st.markdown("**Excel**")
        try:
            st.download_button("⬇️ Complaints Excel",
                               data=export_complaints_excel(filtered),
                               file_name=f"finlyzer_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        except Exception as ex:
            st.error(str(ex))
    with e3:
        st.markdown("**Call log**")
        if not calls_df.empty:
            st.download_button("⬇️ Call log CSV",
                               data=calls_df.to_csv(
                                   index=False).encode("utf-8"),
                               file_name=f"calls_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)

    with st.expander("Preview filtered data"):
        st.dataframe(filtered.head(50), use_container_width=True, height=280)

    st.markdown("---")
    st.markdown("**Notification log**")
    try:
        notifs = get_notifications(DB_PATH)
        if not notifs.empty:
            st.dataframe(notifs, use_container_width=True, height=180)
        else:
            st.info("No notifications sent yet.")
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════════════════
# TAB 7 — USERS
# ══════════════════════════════════════════════════════════════════════════════
with tab_users:
    if not is_admin():
        st.info("User management is for administrators only.")
    else:
        try:
            users_df = get_all_users(DB_PATH)
        except Exception:
            users_df = pd.DataFrame()

        st.markdown("**Current users**")
        if not users_df.empty:
            st.dataframe(users_df, use_container_width=True, height=200)

        st.markdown("**Create new user**")
        with st.form("create_user"):
            uc1, uc2 = st.columns(2)
            uc3, uc4 = st.columns(2)
            nu = uc1.text_input("Username")
            np = uc2.text_input("Password", type="password")
            nr = uc3.selectbox("Role", ["viewer", "admin"])
            ne = uc4.text_input("Email")
            nf = st.text_input("Full name")
            if st.form_submit_button("➕ Create user"):
                if not nu or not np:
                    st.error("Username and password required.")
                elif len(np) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    ok = create_user(nu, np, nr, ne, nf, DB_PATH)
                    if ok:
                        st.success(f"User '{nu}' created.")
                        log_audit("create_user", {"username": nu, "role": nr})
                        st.rerun()
                    else:
                        st.error("Username already exists.")

        if not users_df.empty:
            st.markdown("**Manage users**")
            ud1, ud2, ud3 = st.columns([3, 1, 1])
            target = ud1.selectbox("User", users_df["Username"].tolist())
            if ud2.button("Deactivate"):
                if target == username:
                    st.error("Cannot deactivate yourself.")
                else:
                    deactivate_user(target, DB_PATH)
                    log_audit("deactivate_user", {"target": target})
                    st.success(f"'{target}' deactivated.")
                    st.rerun()
            if ud3.button("Reactivate"):
                reactivate_user(target, DB_PATH)
                log_audit("reactivate_user", {"target": target})
                st.success(f"'{target}' reactivated.")
                st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 8 — MY ACCOUNT
# ══════════════════════════════════════════════════════════════════════════════
with tab_account:
    st.markdown(f"""
    <div style="background:#fff;border:0.5px solid #DDE3EC;border-radius:12px;padding:14px 16px;margin-bottom:12px">
      <div style="font-size:11px;font-weight:700;color:#6B778C;text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px">My profile</div>
      <table style="width:100%;font-size:13px">
        <tr><td style="color:#6B778C;padding:4px 0">Username</td><td style="font-weight:600;text-align:right">{username}</td></tr>
        <tr><td style="color:#6B778C;padding:4px 0">Role</td><td style="text-align:right"><span class="role-badge {role_cls}">{role_label}</span></td></tr>
      </table>
    </div>""", unsafe_allow_html=True)

    st.markdown("**Change password**")
    with st.form("change_pw"):
        op = st.text_input("Current password", type="password")
        np_ = st.text_input("New password", type="password")
        np2 = st.text_input("Confirm new password", type="password")
        if np_:
            strength = sum([len(np_) >= 8, any(c.isupper() for c in np_),
                            any(c.isdigit() for c in np_), any(c in "!@#$%^&*" for c in np_)])
            bar_col = ["#C62828", "#F9A825", "#F9A825",
                       "#00897B", "#00897B"][strength]
            bar_w = ["20%", "40%", "60%", "80%", "100%"][strength]
            lbl = ["Very weak", "Weak", "Fair",
                   "Strong", "Very strong"][strength]
            st.markdown(
                f'<div style="background:#eee;border-radius:4px;height:5px;margin:4px 0">'
                f'<div style="background:{bar_col};width:{bar_w};height:5px;border-radius:4px"></div></div>'
                f'<p style="font-size:11px;color:{bar_col};margin:2px 0 6px">{lbl}</p>',
                unsafe_allow_html=True)
        if st.form_submit_button("🔐 Change password"):
            if not op or not np_ or not np2:
                st.error("All fields required.")
            elif np_ != np2:
                st.error("Passwords do not match.")
            else:
                ok, msg = change_password(username, op, np_, DB_PATH)
                if ok:
                    st.success(msg)
                    log_audit("change_password", {"username": username})
                else:
                    st.error(msg)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 9 — AUDIT
# ══════════════════════════════════════════════════════════════════════════════
with tab_audit:
    if not is_admin():
        st.info("Audit log is for administrators only.")
    else:
        st.markdown("**System audit log** — every action recorded")
        try:
            audit = get_audit_log(300, DB_PATH)
            if audit.empty:
                st.info("No audit records yet.")
            else:
                st.dataframe(audit, use_container_width=True, height=400)
                st.download_button("⬇️ Download audit log",
                                   data=audit.to_csv(
                                       index=False).encode("utf-8"),
                                   file_name=f"audit_{datetime.now().strftime('%Y%m%d')}.csv",
                                   mime="text/csv")
        except Exception as e:
            st.error(str(e))

# ── Session timeout ───────────────────────────────────────────────────────────
if "last_activity" in st.session_state:
    if time.time()-st.session_state.last_activity > 1800:
        st.session_state.authenticated = False
        st.warning("Session expired.")
        st.rerun()
st.session_state.last_activity = time.time()
