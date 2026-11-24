import pandas as pd


def _trend_direction(text: str) -> str:
    """'bull', 'bear' or '' from either trend format.

    The CSV says "... (Bullish)" / "... (Bearish)"; live yfinance data says
    "Above 20 / Below 50 / Above 200". All Above is bullish, all Below is bearish, a mix is neither.
    """
    if "bull" in text:
        return "bull"
    if "bear" in text:
        return "bear"
    above, below = text.count("above"), text.count("below")
    if above and not below:
        return "bull"
    if below and not above:
        return "bear"
    return ""


def _compute_strategy_tag(row) -> str:
    """Compute strategy tag for a single row based on IV rank and trend.

    A missing IV rank (e.g. under a year of history) gets the neutral "Directional Spread".
    """
    iv_rank = pd.to_numeric(row.get("IV Rank (1y)"), errors="coerce")
    raw_trend = row.get("Trend (Above/Below 20/50/200 EMA)")
    trend = "" if raw_trend is None or pd.isna(raw_trend) else str(raw_trend).lower()
    direction = _trend_direction(trend)

    if pd.isna(iv_rank):
        return "Directional Spread"

    if iv_rank >= 50:
        if direction == "bull":
            return "Short Put / Bull Put Spread"
        if direction == "bear":
            return "Bear Call Spread / Iron Condor"
        return "Iron Condor / Short Strangle"

    if iv_rank <= 30:
        if direction == "bull":
            return "Bull Call Debit Spread / Call Calendar"
        if direction == "bear":
            return "Bear Put Debit Spread / Put Calendar"
        return "Straddle / Strangle / Calendar"

    if "range" in trend:
        return "Iron Condor / Butterfly"

    return "Directional Spread"


def compute_strategy_for_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute strategy tags for all tickers in the DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with IV Rank (1y), Trend (Above/Below 20/50/200 EMA), etc.

    Returns
    -------
    pd.DataFrame
        DataFrame with added 'Strategy Tag' column.
    """
    if df.empty:
        return df

    df = df.copy()
    df["Strategy Tag"] = df.apply(_compute_strategy_tag, axis=1)
    return df


def weekly_watchlist(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate a weekly watchlist from scored data, applying strategy tags
    based on IV rank and trend.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with Option Score, IV Rank (1y), Trend, etc.

    Returns
    -------
    pd.DataFrame
        Weekly watchlist with Strategy Tag and Sector columns.
    """
    if df.empty:
        return df

    today = pd.Timestamp.today()

    # An unknown earnings date cannot pass the 14-day buffer, so those tickers are left out.
    # Say so, so a data gap is not mistaken for an earnings conflict.
    unknown = int(((df["Option Score"] >= 6) & df["Next Earnings Date"].isna()).sum())
    if unknown:
        print(
            f"[INFO] {unknown} ticker(s) scoring 6+ left off the watchlist: earnings date unknown."
        )

    weekly = df[
        (df["Option Score"] >= 6) & (df["Next Earnings Date"] > today + pd.Timedelta(days=14))
    ].copy()

    if weekly.empty:
        return weekly

    weekly["Strategy Tag"] = weekly.apply(_compute_strategy_tag, axis=1)

    # Normalize date column to "Date"
    if "date" in weekly.columns and "Date" not in weekly.columns:
        weekly = weekly.rename(columns={"date": "Date"})
    elif "Date" not in weekly.columns:
        weekly["Date"] = today

    return weekly[
        [
            "Ticker",
            "Date",
            "Sector",
            "Price",
            "Option Score",
            "IV Rank (1y)",
            "IV 30d",
            "Next Earnings Date",
            "Trend (Above/Below 20/50/200 EMA)",
            "Strategy Tag",
        ]
    ].rename(columns={"Trend (Above/Below 20/50/200 EMA)": "Trend"})
