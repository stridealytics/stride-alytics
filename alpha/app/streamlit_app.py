"""
Streamlit dashboard for the Option Trading System.

Displays daily metrics, option scores, volatility data, and trades
from Supabase (real scanned data).
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.supabase_client import get_supabase_client
from app.utils.date_utils import format_date_mmm_dd_yyyy

_PAGE_SIZE = 1000  # Supabase/PostgREST returns at most 1000 rows per request


def _load_from_supabase(table: str) -> pd.DataFrame:
    """Load the most recent day's rows from ``table``.

    Only the latest ``date`` is returned (the tables hold one snapshot per day),
    and results are paged so the 1000-row API limit never silently truncates them.
    """
    try:
        client = get_supabase_client()

        latest_resp = client.table(table).select("date").order("date", desc=True).limit(1).execute()
        latest = (latest_resp.data or [{}])[0].get("date")
        if not latest:
            return pd.DataFrame()
        day = str(latest)[:10]

        rows: list[dict] = []
        start = 0
        while True:
            page = (
                client.table(table)
                .select("*")
                .like("date", f"{day}%")
                .range(start, start + _PAGE_SIZE - 1)
                .execute()
                .data
                or []
            )
            rows.extend(page)
            if len(page) < _PAGE_SIZE:
                break
            start += _PAGE_SIZE
        return pd.DataFrame(rows)
    except Exception as e:
        st.warning(f"Failed to load {table} from Supabase: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=600)  # data changes once a day; fewer Supabase reads
def get_daily_metrics() -> pd.DataFrame:
    """Load daily metrics from Supabase - already contains all computed fields."""
    daily = _load_from_supabase("daily_metrics")
    return daily


@st.cache_data(ttl=600)  # data changes once a day; fewer Supabase reads
def get_option_scores() -> pd.DataFrame:
    """Load option scores - uses daily_metrics which has all computed fields."""
    df = _load_from_supabase("daily_metrics")
    if df.empty:
        return pd.DataFrame()

    # Normalize date format for display
    if "date" in df.columns:
        df["date"] = df["date"].astype(str).str[:10]

    # Rename to display columns
    df = df.rename(
        columns={
            "ticker": "Ticker",
            "date": "Date",
            "option_score": "Option Score",
            "trend": "Trend",
            "strategy": "Strategy Tag",
            "band": "Band",
        }
    )

    # Format Date column
    if "Date" in df.columns:
        df["Date"] = df["Date"].apply(format_date_mmm_dd_yyyy)

    # Return only the columns we need for this tab
    cols_needed = ["Ticker", "Date", "Option Score", "Trend", "Strategy Tag", "Band"]
    available = [c for c in cols_needed if c in df.columns]
    return df[available].copy()


@st.cache_data(ttl=600)
def get_trades() -> pd.DataFrame:
    return pd.DataFrame()


def _normalize_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Make a copy to avoid modifying the original DataFrame
    df = df.copy()

    # Normalize date column to string format for consistent merging
    if "date" in df.columns:
        df["date"] = df["date"].astype(str).str[:10]  # Take just YYYY-MM-DD part
    if "next_earnings_date" in df.columns:
        df["next_earnings_date"] = df["next_earnings_date"].astype(str).str[:10]

    rename_map = {
        "ticker": "Ticker",
        "date": "Date",
        "price": "Price",
        "option_volume": "Option Volume",
        "max_oi_near_exp": "Max OI (Near Exp)",
        "bid_ask_spread_pct": "Bid-Ask Spread %",
        "iv_30d": "IV 30d",
        "iv_rank_1y": "IV Rank (1y)",
        "hv_30d": "HV 30d",
        "atr": "ATR",
        "next_earnings_date": "Next Earnings Date",
        "short_interest_pct": "Short Interest %",
        "revenue_growth_yoy": "Revenue Growth (YoY)",
        "debt_equity": "Debt/Equity",
        "quality_score": "Quality Score (1-5)",
        "option_score": "Option Score",
        "band": "Band",
        "trend": "Trend (Above/Below 20/50/200 EMA)",
        "strategy": "Strategy Tag",
        "sector": "Sector",
    }
    df = df.rename(columns=rename_map)

    # Format Date columns after rename
    if "Date" in df.columns:
        df["Date"] = df["Date"].apply(format_date_mmm_dd_yyyy)
    if "Next Earnings Date" in df.columns:
        df["Next Earnings Date"] = df["Next Earnings Date"].apply(format_date_mmm_dd_yyyy)

    # Compute Volatility Bias and IV vs HV columns
    if "IV Rank (1y)" in df.columns:

        def vol_bias(val):
            if pd.isna(val):
                return "N/A"
            if val >= 50:
                return "Sell Premium"
            if val <= 30:
                return "Buy Premium"
            return "Neutral"

        df["Volatility Bias"] = df["IV Rank (1y)"].apply(vol_bias)

    if "IV 30d" in df.columns and "HV 30d" in df.columns:

        def iv_vs_hv(row):
            iv_30d = row.get("IV 30d")
            hv_30d = row.get("HV 30d")
            if pd.isna(iv_30d) or pd.isna(hv_30d):
                return "N/A"
            if iv_30d > hv_30d:
                return "IV > HV (Selling better)"
            if iv_30d < hv_30d:
                return "IV < HV (Buying better)"
            return "IV ≈ HV"

        df["IV vs HV"] = df.apply(iv_vs_hv, axis=1)

    return df


st.markdown(
    """
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; }
    h1 { font-size: 1.75rem; margin-top: 0; margin-bottom: 0.5rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.set_page_config(
    page_title="Option Trading System", layout="wide", page_icon="assets/icon/favicon.ico"
)


def _require_password() -> None:
    """Gate the dashboard behind DASHBOARD_PASSWORD (Streamlit secret or env var).

    Streamlit Community Cloud apps are public by default. With no password configured the app
    still opens (local use) but shows a warning, so a public deployment is never silent.
    """
    import hmac
    import os

    expected = os.getenv("DASHBOARD_PASSWORD")
    try:
        expected = expected or st.secrets.get("DASHBOARD_PASSWORD")
    except Exception:  # noqa: BLE001 - no secrets file locally
        pass
    if not expected:
        st.warning("DASHBOARD_PASSWORD is not set: this dashboard is open to anyone with the link.")
        return
    if st.session_state.get("_authed"):
        return
    entered = st.text_input("Password", type="password")
    if entered and hmac.compare_digest(entered.encode(), str(expected).encode()):
        st.session_state["_authed"] = True
        st.rerun()
    elif entered:
        st.error("Wrong password.")
    st.stop()


_require_password()
st.markdown("# StrideAlytics Alpha Dashboard")

# Load data once at startup
raw = get_daily_metrics()
df = _normalize_daily_metrics(raw)

tab1, tab2, tab3, tab4 = st.tabs(["Screener", "Bands & Scores", "Volatility", "Trades"])

with tab1:
    st.subheader("Screener (Daily Metrics)")
    if not df.empty:
        display_cols = [
            "Ticker",
            "Price",
            "Option Score",
            "Band",
            "Strategy Tag",
            "Trend (Above/Below 20/50/200 EMA)",
            "IV 30d",
            "IV Rank (1y)",
            "HV 30d",
            "Option Volume",
            "Max OI (Near Exp)",
            "Bid-Ask Spread %",
            "ATR",
            "Next Earnings Date",
            "Short Interest %",
            "Quality Score (1-5)",
        ]
        available = [c for c in display_cols if c in df.columns]
        st.dataframe(df[available], width="stretch")
    else:
        st.info("No daily metrics found.")

with tab2:
    st.subheader("Bands & Option Scores")
    scores = get_option_scores()
    if not scores.empty:
        score_cols = ["Ticker", "Date", "Option Score", "Trend", "Strategy Tag", "Band"]
        available = [c for c in score_cols if c in scores.columns]
        st.dataframe(scores[available], width="stretch")
    else:
        st.info("No option scores found.")

with tab3:
    st.subheader("Volatility (IV vs HV)")
    if not raw.empty:
        vol_cols = [
            "Ticker",
            "Date",
            "IV 30d",
            "IV Rank (1y)",
            "HV 30d",
            "ATR",
            "Next Earnings Date",
            "Sector",
            "Volatility Bias",
            "IV vs HV",
        ]
        available = [c for c in vol_cols if c in df.columns]
        if available:
            st.dataframe(df[available], width="stretch")
        else:
            st.warning("Volatility columns missing in daily_metrics.")
    else:
        st.info("No daily metrics found.")

with tab4:
    st.subheader("Trades & P&L")
    trades = get_trades()
    if not trades.empty:
        st.dataframe(trades, width="stretch")
    else:
        st.info("No trades found.")
