import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))  

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))  

from src.auth import require_auth, is_admin, is_viewer
from src.db import (
    get_db_path, get_all_complaints,
    log_call, update_complaints_bulk,
)
from src.utils import atomic_write_csv, atomic_write_json
from src.clustering import cluster_texts
from src.preprocessing import preprocess_text
from src.data_input import load_data
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
import pandas as pd
from datetime import datetime, date
import time
import logging
import json
import uuid
import sys
import os
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def log_audit(action: str, details: dict):
    user = st.session_state.get("username", "Unknown")
    role = st.session_state.get("role", "Unknown")
    logging.info("AUDIT: %s (%s) — %s — %s", user, role, action, details)


def status_badge(status: str) -> str:
    colours = {
        "Resolved":  ("#00875A", "#E3FCEF"),
        "Pending":   ("#FF8B00", "#FFFAE6"),
        "Escalated": ("#DE350B", "#FFEBE6"),
    }
    fg, bg = colours.get(status, ("#172B4D", "#F4F5F7"))
    return (
        f'<span style="background:{bg};color:{fg};padding:3px 10px;'
        f'border-radius:12px;font-size:12px;font-weight:600;">{status}</span>'
    )

# ---------------------------------------------------------------------------
# Page config + global CSS
# ---------------------------------------------------------------------------


st.set_page_config(
    page_title="Finlyzer — Banking Intelligence",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
/* ── Brand colours ──────────────────────────────────────────── */
:root {
  --navy:   #0A2342;
  --blue:   #1565C0;
  --teal:   #00897B;
  --gold:   #F9A825;
  --danger: #C62828;
  --light:  #F8FAFD;
  --border: #DDE3EC;
  --text:   #172B4D;
  --muted:  #6B778C;
}

/* ── Hide default Streamlit chrome ───────────────────────────── */
#MainMenu, footer, header {visibility: hidden;}
.block-container {padding-top: 1.2rem !important;}

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--navy) !important;
  border-right: none;
}
[data-testid="stSidebar"] * {color: #CBD5E0 !important;}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stMultiSelect label,
[data-testid="stSidebar"] .stTextInput label,
[data-testid="stSidebar"] .stDateInput label {
  color: #90A4AE !important; font-size: 12px !important;
}
[data-testid="stSidebar"] h1,
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: #FFFFFF !important; font-size: 13px !important;
  text-transform: uppercase; letter-spacing: 1px;
}
[data-testid="stSidebar"] .stButton button {
  background: #1565C0 !important; color: #fff !important;
  border: none !important; width: 100%;
}

/* ── KPI metric cards ────────────────────────────────────────── */
.kpi-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 24px;
  position: relative;
  overflow: hidden;
}
.kpi-card::before {
  content: "";
  position: absolute; top: 0; left: 0;
  width: 4px; height: 100%;
  background: var(--accent, var(--blue));
}
.kpi-label {
  font-size: 11px; font-weight: 600;
  color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.8px; margin-bottom: 8px;
}
.kpi-value {
  font-size: 32px; font-weight: 700;
  color: var(--text); line-height: 1;
}
.kpi-sub {
  font-size: 12px; color: var(--muted); margin-top: 6px;
}

/* ── Section cards ───────────────────────────────────────────── */
.fin-card {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 16px;
}
.fin-card-title {
  font-size: 13px; font-weight: 700;
  color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.8px; margin-bottom: 14px;
  padding-bottom: 10px; border-bottom: 1px solid var(--border);
}

/* ── Complaint row ───────────────────────────────────────────── */
.complaint-detail {
  background: var(--light);
  border-left: 4px solid var(--blue);
  border-radius: 6px;
  padding: 14px 16px;
  font-size: 14px; color: var(--text);
  line-height: 1.6; margin: 10px 0;
}
.detail-row {
  display: flex; justify-content: space-between;
  padding: 6px 0; border-bottom: 1px solid var(--border);
  font-size: 13px;
}
.detail-row:last-child {border-bottom: none;}
.detail-key {color: var(--muted); font-weight: 500;}
.detail-val {color: var(--text); font-weight: 600; text-align: right;}

/* ── Page header ─────────────────────────────────────────────── */
.page-header {
  background: linear-gradient(135deg, var(--navy) 0%, #1565C0 100%);
  border-radius: 14px; padding: 24px 32px;
  margin-bottom: 24px; color: #fff;
  display: flex; align-items: center; gap: 16px;
}
.page-header h1 {
  font-size: 24px; font-weight: 700; margin: 0;
  color: #fff !important;
}
.page-header p {font-size: 13px; color: #90CAF9; margin: 4px 0 0;}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
  gap: 4px; border-bottom: 2px solid var(--border);
}
.stTabs [data-baseweb="tab"] {
  font-size: 13px; font-weight: 600;
  color: var(--muted) !important;
  padding: 8px 20px; border-radius: 8px 8px 0 0;
}
.stTabs [aria-selected="true"] {
  color: var(--blue) !important;
  border-bottom: 2px solid var(--blue) !important;
}

/* ── Form buttons ────────────────────────────────────────────── */
.stButton button {
  background: var(--blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  padding: 8px 20px !important;
}
.stButton button:hover {
  background: #0D47A1 !important;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(21,101,192,0.3) !important;
}

/* ── Plotly chart containers ─────────────────────────────────── */
.js-plotly-plot {border-radius: 10px; overflow: hidden;}

/* ── Role badge ──────────────────────────────────────────────── */
.role-badge {
  display: inline-block;
  padding: 4px 12px; border-radius: 20px;
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.5px;
}
.role-admin {background: #E8F5E9; color: #2E7D32;}
.role-viewer {background: #E3F2FD; color: #1565C0;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar branding
# ---------------------------------------------------------------------------

st.sidebar.markdown("""
<div style="text-align:center;padding:20px 0 24px;">
  <div style="font-size:36px;">🏦</div>
  <div style="color:#fff;font-size:18px;font-weight:700;letter-spacing:1px;">FINLYZER</div>
  <div style="color:#90A4AE;font-size:11px;margin-top:2px;">Banking Intelligence Platform</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

authenticated, role = require_auth()
if not authenticated:
    st.stop()

username = st.session_state.get("username", "User")
role_label = st.session_state.get("role", "viewer")

role_cls = "role-admin" if role_label == "admin" else "role-viewer"
st.sidebar.markdown(
    f'<div style="text-align:center;padding-bottom:16px;">'
    f'<span class="role-badge {role_cls}">{role_label}</span>'
    f'<div style="color:#CBD5E0;font-size:12px;margin-top:6px;">👤 {username}</div>'
    f'</div>',
    unsafe_allow_html=True,
)

if st.sidebar.button("🚪 Logout"):
    st.session_state.authenticated = False
    st.session_state.role = None
    st.session_state.username = None
    st.rerun()

st.sidebar.markdown(
    "<hr style='border-color:#1E3A5F;margin:8px 0 16px'>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_PATH = os.path.join(BASE, "data", "failed_transactions.csv")
CUSTOMERS_PATH = os.path.join(BASE, "data", "data_customers.csv")
CALLS_PATH = os.path.join(BASE, "data", "calls_log.csv")
DB_PATH = get_db_path()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

df = None
if os.path.exists(DB_PATH):
    try:
        df = get_all_complaints(DB_PATH)
    except Exception as e:
        st.error(f"Database error: {e}")

if df is None or df.empty:
    try:
        df = load_data(DATA_PATH)
    except Exception as e:
        st.error(f"Data load error: {e}")
        df = None

customers = None
if os.path.exists(CUSTOMERS_PATH):
    try:
        customers = pd.read_csv(CUSTOMERS_PATH)
    except Exception:
        pass

if df is not None and not df.empty:
    for col in ("Transaction_Date", "Complaint_Date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    if customers is not None and "Customer_ID" in customers.columns:
        contact_cols = [c for c in ["Customer_Email", "Phone"]
                        if c in customers.columns]
        if contact_cols:
            df = df.merge(
                customers[["Customer_ID"] +
                          contact_cols].drop_duplicates("Customer_ID"),
                on="Customer_ID", how="left"
            )
    if "Customer_Email" not in df.columns:
        df["Customer_Email"] = ""
    if "Phone" not in df.columns:
        df["Phone"] = ""

_calls_cols = ["Call_ID", "Complaint_ID", "Customer_ID", "Call_Date",
               "Agent", "Outcome", "Notes", "Escalated", "Follow_Up_Date"]
if os.path.exists(CALLS_PATH):
    try:
        calls_df = pd.read_csv(CALLS_PATH, parse_dates=["Call_Date"])
    except Exception:
        calls_df = pd.DataFrame(columns=_calls_cols)
else:
    calls_df = pd.DataFrame(columns=_calls_cols)

if df is None or df.empty:
    st.markdown("""
    <div class="page-header">
      <div style="font-size:40px;">🏦</div>
      <div><h1>Finlyzer</h1><p>Place failed_transactions.csv in the data/ folder and restart.</p></div>
    </div>""", unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

st.sidebar.markdown("### 🔍 Filters")
min_date = df["Complaint_Date"].min().date()
max_date = df["Complaint_Date"].max().date()
date_range = st.sidebar.date_input("Date range", value=(min_date, max_date))

all_channels = sorted(df["Channel"].dropna().unique())
channels = st.sidebar.multiselect(
    "Channel", all_channels, default=all_channels)

all_statuses = sorted(df["Status"].dropna().unique())
statuses = st.sidebar.multiselect("Status", all_statuses, default=all_statuses)

search = st.sidebar.text_input(
    "🔎 Search issues", placeholder="e.g. ATM, transfer…")

st.sidebar.markdown(
    "<hr style='border-color:#1E3A5F;margin:16px 0'>", unsafe_allow_html=True)
st.sidebar.markdown("### ⚙️ Cluster settings")
cluster_n = st.sidebar.slider("Number of clusters", 2, 10, 5)
max_features = st.sidebar.slider("TF-IDF features", 500, 5000, 2000, step=500)

# ---------------------------------------------------------------------------
# Apply filters
# ---------------------------------------------------------------------------

start_d, end_d = date_range if len(date_range) == 2 else (min_date, max_date)
mask = df["Complaint_Date"].dt.date.between(start_d, end_d)
mask &= df["Channel"].isin(channels)
mask &= df["Status"].isin(statuses)
if search:
    mask &= df["Issue"].str.contains(search, case=False, na=False)
filtered = df.loc[mask].copy()

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown(f"""
<div class="page-header">
  <div style="font-size:44px;">🏦</div>
  <div>
    <h1>Finlyzer — Banking Intelligence</h1>
    <p>AI-powered complaint analysis · {len(filtered):,} complaints in view · {datetime.now().strftime("%d %b %Y")}</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI row
# ---------------------------------------------------------------------------

total = len(filtered)
resolved = int((filtered["Status"] == "Resolved").sum())
pending = int((filtered["Status"] == "Pending").sum())
escalated = int((filtered["Status"] == "Escalated").sum())
res_rate = f"{resolved/total*100:.1f}%" if total else "0%"
avg_res = pd.to_numeric(filtered.get(
    "Resolution_Time", pd.Series(dtype=float)), errors="coerce").dropna()
avg_res_str = f"{avg_res.mean():.1f}d" if not avg_res.empty else "—"

k1, k2, k3, k4, k5 = st.columns(5)
kpis = [
    (k1, "Total Complaints", f"{total:,}", f"{start_d} → {end_d}", "#1565C0"),
    (k2, "Resolved",         f"{resolved:,}",
     f"Resolution rate: {res_rate}", "#00897B"),
    (k3, "Pending",          f"{pending:,}",  "Awaiting action", "#F9A825"),
    (k4, "Escalated",        f"{escalated:,}",
     "Needs urgent attention", "#C62828"),
    (k5, "Avg Resolution",   avg_res_str,     "Days to close", "#5C35CC"),
]
accents = ["#1565C0", "#00897B", "#F9A825", "#C62828", "#5C35CC"]

for (col, label, value, sub, accent), acc in zip(kpis, accents):
    with col:
        st.markdown(f"""
        <div class="kpi-card" style="--accent:{acc}">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value" style="color:{acc}">{value}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "📊  Analytics", "🔍  Complaint Detail", "🤖  AI Clustering", "📞  Call Log"
])

CHART_THEME = "plotly_white"
PALETTE = px.colors.qualitative.Bold

# ── TAB 1: Analytics ────────────────────────────────────────────────────────
with tab1:
    r1c1, r1c2 = st.columns([3, 2])

    with r1c1:
        st.markdown('<div class="fin-card">'
                    '<div class="fin-card-title">Complaints over time</div>', unsafe_allow_html=True)
        ts = filtered.groupby(filtered["Complaint_Date"].dt.to_period(
            "W").dt.start_time).size().reset_index(name="count")
        fig_ts = px.area(ts, x="Complaint_Date", y="count",
                         color_discrete_sequence=["#1565C0"])
        fig_ts.update_traces(
            fill="tozeroy", fillcolor="rgba(21,101,192,0.08)", line_width=2)
        fig_ts.update_layout(
            template=CHART_THEME, margin=dict(l=0, r=0, t=10, b=0),
            xaxis_title="", yaxis_title="Complaints",
            plot_bgcolor="#fff", paper_bgcolor="#fff",
            font=dict(family="Inter, sans-serif", size=12),
            height=240,
        )
        st.plotly_chart(fig_ts, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with r1c2:
        st.markdown('<div class="fin-card">'
                    '<div class="fin-card-title">By channel</div>', unsafe_allow_html=True)
        chan = filtered["Channel"].value_counts().reset_index()
        chan.columns = ["Channel", "Count"]
        fig_pie = px.pie(chan, names="Channel", values="Count",
                         color_discrete_sequence=PALETTE, hole=0.55)
        fig_pie.update_layout(
            template=CHART_THEME, margin=dict(l=0, r=0, t=10, b=0),
            showlegend=True, legend=dict(orientation="v", x=1, y=0.5),
            plot_bgcolor="#fff", paper_bgcolor="#fff",
            font=dict(family="Inter, sans-serif", size=12),
            height=240,
        )
        fig_pie.update_traces(textinfo="percent", textfont_size=11)
        st.plotly_chart(fig_pie, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    r2c1, r2c2 = st.columns([2, 3])

    with r2c1:
        st.markdown('<div class="fin-card">'
                    '<div class="fin-card-title">Status breakdown</div>', unsafe_allow_html=True)
        stat_counts = filtered["Status"].value_counts().reset_index()
        stat_counts.columns = ["Status", "Count"]
        stat_colours = {"Resolved": "#00897B",
                        "Pending": "#F9A825", "Escalated": "#C62828"}
        fig_status = px.bar(stat_counts, x="Status", y="Count",
                            color="Status", color_discrete_map=stat_colours,
                            text="Count")
        fig_status.update_layout(
            template=CHART_THEME, margin=dict(l=0, r=0, t=10, b=0),
            showlegend=False, plot_bgcolor="#fff", paper_bgcolor="#fff",
            font=dict(family="Inter, sans-serif", size=12), height=260,
        )
        fig_status.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig_status, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with r2c2:
        st.markdown('<div class="fin-card">'
                    '<div class="fin-card-title">Top complaint issues</div>', unsafe_allow_html=True)
        top_n = 8
        top_issues = filtered["Issue"].value_counts().nlargest(
            top_n).reset_index()
        top_issues.columns = ["Issue", "Count"]
        # Truncate long issue text
        top_issues["Issue"] = top_issues["Issue"].str[:55]
        fig_bar = px.bar(top_issues, x="Count", y="Issue", orientation="h",
                         color="Count", color_continuous_scale=["#90CAF9", "#1565C0"],
                         text="Count")
        fig_bar.update_layout(
            template=CHART_THEME, margin=dict(l=0, r=0, t=10, b=0),
            yaxis=dict(autorange="reversed"),
            coloraxis_showscale=False,
            plot_bgcolor="#fff", paper_bgcolor="#fff",
            font=dict(family="Inter, sans-serif", size=11), height=260,
        )
        fig_bar.update_traces(textposition="outside", marker_line_width=0)
        st.plotly_chart(fig_bar, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # Channel × Status heatmap
    st.markdown('<div class="fin-card">'
                '<div class="fin-card-title">Channel × Status heatmap</div>', unsafe_allow_html=True)
    heat = filtered.groupby(["Channel", "Status"]
                            ).size().reset_index(name="Count")
    heat_pivot = heat.pivot(
        index="Channel", columns="Status", values="Count").fillna(0)
    fig_heat = px.imshow(
        heat_pivot, color_continuous_scale=["#EFF6FF", "#1565C0"],
        text_auto=True, aspect="auto",
    )
    fig_heat.update_layout(
        template=CHART_THEME, margin=dict(l=0, r=0, t=10, b=0),
        plot_bgcolor="#fff", paper_bgcolor="#fff",
        font=dict(family="Inter, sans-serif", size=12), height=200,
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig_heat, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── TAB 2: Complaint Detail ──────────────────────────────────────────────────
with tab2:
    if filtered.empty:
        st.info("No complaints match the current filters.")
    else:
        dc1, dc2 = st.columns([2, 3])

        with dc1:
            st.markdown('<div class="fin-card-title" style="font-size:13px;font-weight:700;'
                        'color:#6B778C;text-transform:uppercase;letter-spacing:.8px;">'
                        'Select complaint</div>', unsafe_allow_html=True)
            complaint_sel = st.selectbox(
                "Complaint ID", options=filtered["Complaint_ID"].tolist(), label_visibility="collapsed"
            )
            comp_row = filtered[filtered["Complaint_ID"]
                                == complaint_sel].iloc[0]

            status = comp_row["Status"]
            st.markdown(f"""
            <div class="fin-card" style="margin-top:12px;">
              <div class="fin-card-title">Complaint summary</div>
              <div class="detail-row"><span class="detail-key">ID</span>
                <span class="detail-val">{comp_row['Complaint_ID']}</span></div>
              <div class="detail-row"><span class="detail-key">Customer</span>
                <span class="detail-val">{comp_row['Customer_ID']}</span></div>
              <div class="detail-row"><span class="detail-key">Channel</span>
                <span class="detail-val">{comp_row['Channel']}</span></div>
              <div class="detail-row"><span class="detail-key">Amount (₦)</span>
                <span class="detail-val">₦{float(comp_row.get('Amount',0)):,.2f}</span></div>
              <div class="detail-row"><span class="detail-key">Complaint date</span>
                <span class="detail-val">{str(comp_row.get('Complaint_Date',''))[:10]}</span></div>
              <div class="detail-row"><span class="detail-key">Status</span>
                <span class="detail-val">{status_badge(status)}</span></div>
              <div class="detail-row"><span class="detail-key">Email</span>
                <span class="detail-val" style="font-size:12px">{comp_row.get('Customer_Email','—')}</span></div>
              <div class="detail-row"><span class="detail-key">Phone</span>
                <span class="detail-val">{comp_row.get('Phone','—')}</span></div>
            </div>
            """, unsafe_allow_html=True)

        with dc2:
            st.markdown('<div class="fin-card">'
                        '<div class="fin-card-title">Issue description</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="complaint-detail">{comp_row["Issue"]}</div>',
                unsafe_allow_html=True,
            )
            st.markdown('</div>', unsafe_allow_html=True)

            # Call history
            st.markdown('<div class="fin-card"><div class="fin-card-title">Call history</div>',
                        unsafe_allow_html=True)
            related = calls_df[
                (calls_df["Complaint_ID"] == complaint_sel) |
                (calls_df["Customer_ID"] == comp_row["Customer_ID"])
            ]
            if related.empty:
                st.markdown('<p style="color:#6B778C;font-size:13px;">No calls logged yet.</p>',
                            unsafe_allow_html=True)
            else:
                st.dataframe(
                    related.sort_values(
                        "Call_Date", ascending=False).reset_index(drop=True),
                    use_container_width=True, height=180,
                )
            st.markdown('</div>', unsafe_allow_html=True)

            # Log a call
            st.markdown('<div class="fin-card"><div class="fin-card-title">Log a call</div>',
                        unsafe_allow_html=True)
            with st.form("log_call_form"):
                fc1, fc2 = st.columns(2)
                with fc1:
                    agent = st.text_input("Agent name",
                                          value=st.session_state.get("username", "") if not is_admin() else "")
                with fc2:
                    outcome = st.selectbox("Outcome",
                                           ["Answered", "No answer", "Voicemail", "Callback requested", "Escalated"])
                notes = st.text_area(
                    "Notes", placeholder="Summarise the call…", height=80)
                fc3, fc4 = st.columns(2)
                with fc3:
                    escalate = st.checkbox("Escalate complaint",
                                           value=(comp_row["Status"] != "Escalated") if is_admin() else (outcome == "Escalated"))
                with fc4:
                    follow_up = st.date_input("Follow-up date", value=None)

                if st.form_submit_button("💾  Save call", disabled=not is_viewer()):
                    new_call = {
                        "Call_ID": str(uuid.uuid4()),
                        "Complaint_ID": complaint_sel,
                        "Customer_ID":  comp_row["Customer_ID"],
                        "Call_Date":    datetime.utcnow().isoformat(),
                        "Agent": agent, "Outcome": outcome,
                        "Notes": notes, "Escalated": bool(escalate),
                        "Follow_Up_Date": follow_up.isoformat() if isinstance(follow_up, date) else "",
                    }
                    try:
                        if os.path.exists(DB_PATH):
                            log_call(new_call, db_path=DB_PATH)
                        else:
                            calls_df2 = pd.concat(
                                [calls_df, pd.DataFrame([new_call])], ignore_index=True)
                            atomic_write_csv(calls_df2, CALLS_PATH)
                        st.success("✅ Call logged successfully.")
                        log_audit(
                            "log_call", {"complaint_id": complaint_sel, "outcome": outcome})
                    except Exception as e:
                        st.error(f"Failed to save: {e}")
            st.markdown('</div>', unsafe_allow_html=True)

        # Admin bulk actions
        if is_admin():
            st.markdown('<div class="fin-card"><div class="fin-card-title">Bulk actions</div>',
                        unsafe_allow_html=True)
            ba1, ba2, ba3 = st.columns([3, 2, 1])
            with ba1:
                sel_ids = st.multiselect(
                    "Select complaint(s)", filtered["Complaint_ID"].tolist())
            with ba2:
                bulk_action = st.selectbox(
                    "Action", ["(none)", "Set Status", "Set Channel", "Assign Agent"])
            with ba3:
                if bulk_action == "Set Status":
                    bulk_val = st.selectbox(
                        "Value", ["Pending", "Resolved", "Escalated"])
                elif bulk_action == "Set Channel":
                    bulk_val = st.selectbox("Value", sorted(
                        df["Channel"].dropna().unique()))
                else:
                    bulk_val = st.text_input("Value")

            if st.button("⚡ Apply", disabled=(not sel_ids or bulk_action == "(none)")):
                if bulk_action == "Set Status":
                    df.loc[df["Complaint_ID"].isin(
                        sel_ids), "Status"] = bulk_val
                elif bulk_action == "Set Channel":
                    df.loc[df["Complaint_ID"].isin(
                        sel_ids), "Channel"] = bulk_val
                st.session_state["edited_df"] = df
                st.success(f"Updated {len(sel_ids)} complaint(s).")
                log_audit(f"bulk_{bulk_action}", {
                          "ids": sel_ids, "value": bulk_val})
            st.markdown('</div>', unsafe_allow_html=True)

        # Commit
        if st.button("💾  Commit all changes to database"):
            try:
                updates = st.session_state.get("edited_df", df)
                updates = updates[updates["Complaint_ID"].notna()]
                if os.path.exists(DB_PATH):
                    update_complaints_bulk(updates, db_path=DB_PATH)
                    st.success("✅ Changes saved to database.")
                else:
                    atomic_write_csv(updates, DATA_PATH)
                    st.success("✅ Changes saved to CSV.")
                st.session_state.pop("edited_df", None)
            except Exception as e:
                st.error(f"Commit failed: {e}")

# ── TAB 3: AI Clustering ────────────────────────────────────────────────────
with tab3:
    st.markdown('<div class="fin-card"><div class="fin-card-title">'
                '🤖 AI root-cause clustering</div>', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:13px;color:#6B778C;margin-bottom:16px;">'
        'Uses TF-IDF + K-Means to group similar complaints and surface root causes. '
        'Each cluster represents a distinct category of issues your customers face.</p>',
        unsafe_allow_html=True,
    )

    if st.button("🚀  Run AI clustering now"):
        with st.spinner("Analysing complaints with AI…"):
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
                plot_df = filtered.reset_index(drop=True).copy()
                plot_df["Cluster"] = [f"Cluster {l+1}" for l in labels]
                plot_df["x"] = coords[:, 0]
                plot_df["y"] = coords[:, 1]
                st.session_state["clustered_df"] = plot_df

                # Cluster summary table
                summary = plot_df.groupby("Cluster").agg(
                    Count=("Complaint_ID", "count"),
                    Resolved=("Status", lambda s: (s == "Resolved").sum()),
                    Escalated=("Status", lambda s: (s == "Escalated").sum()),
                ).reset_index()
                summary["Resolution %"] = (
                    summary["Resolved"]/summary["Count"]*100).round(1).astype(str) + "%"
                st.dataframe(summary, use_container_width=True, height=200)

    if "clustered_df" in st.session_state:
        plot_df = st.session_state["clustered_df"]
        fig_scatter = px.scatter(
            plot_df, x="x", y="y",
            color="Cluster",
            color_discrete_sequence=PALETTE,
            hover_data=["Complaint_ID", "Issue",
                        "Channel", "Status", "Cluster"],
            title="Complaint clusters — 2D projection",
            height=480,
        )
        fig_scatter.update_traces(marker=dict(
            size=9, opacity=0.85, line=dict(width=0.5, color="#fff")))
        fig_scatter.update_layout(
            template=CHART_THEME,
            plot_bgcolor="#F8FAFD", paper_bgcolor="#fff",
            font=dict(family="Inter, sans-serif", size=12),
            margin=dict(l=0, r=0, t=40, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

# ── TAB 4: Call Log ──────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="fin-card"><div class="fin-card-title">All call records</div>',
                unsafe_allow_html=True)
    if calls_df.empty:
        st.markdown('<p style="color:#6B778C;font-size:13px;">No calls have been logged yet. '
                    'Use the Complaint Detail tab to log calls.</p>', unsafe_allow_html=True)
    else:
        st.dataframe(
            calls_df.sort_values(
                "Call_Date", ascending=False).reset_index(drop=True),
            use_container_width=True,
        )
        cl1, cl2, cl3 = st.columns(3)
        cl1.metric("Total calls", len(calls_df))
        cl2.metric("Escalated", int(calls_df["Escalated"].sum()))
        if "Outcome" in calls_df.columns:
            cl3.metric("Most common outcome", calls_df["Outcome"].mode()[
                       0] if not calls_df.empty else "—")
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session timeout
# ---------------------------------------------------------------------------

if "last_activity" in st.session_state:
    if time.time() - st.session_state.last_activity > 1800:
        st.session_state.authenticated = False
        st.warning("Session expired. Please log in again.")
        st.rerun()
st.session_state.last_activity = time.time()
