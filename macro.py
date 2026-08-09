"""Daily macro and sector-regime snapshot using liquid market proxies."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import requests

from network import configure_tls


WATCHLIST = {
    "S&P 500": "SPY",
    "Nasdaq 100": "QQQ",
    "Small caps": "IWM",
    "Semiconductors": "SMH",
    "Technology": "XLK",
    "Financials": "XLF",
    "Energy": "XLE",
    "Health care": "XLV",
    "Long bonds": "TLT",
    "High yield credit": "HYG",
    "US dollar": "DX-Y.NYB",
    "Gold": "GLD",
    "Bitcoin": "BTC-USD",
}
SNAPSHOT_COLUMNS = ["Asset", "Ticker", "Last", "1D", "1M", "AsOf"]
WEEKLY_SNAPSHOT_COLUMNS = ["Asset", "Ticker", "WeekStart", "Last", "1W", "1M", "AsOf"]


@dataclass(frozen=True)
class Regime:
    label: str
    explanation: str


def market_snapshot() -> tuple[pd.DataFrame, list[str]]:
    configure_tls()
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for label, ticker in WATCHLIST.items():
        try:
            encoded = requests.utils.quote(ticker, safe="")
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}",
                params={"range": "3mo", "interval": "1d", "events": "div,splits"},
                headers={"User-Agent": "Mozilla/5.0 InvestorOS/1.0"}, timeout=20,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            closes = [value for value in result["indicators"]["quote"][0]["close"] if value is not None]
            if len(closes) < 22:
                warnings.append(f"{ticker}: insufficient history.")
                continue
            last = float(closes[-1])
            day = float(last / closes[-2] - 1)
            month = float(last / closes[-22] - 1)
            as_of = pd.to_datetime(result["timestamp"][-1], unit="s", utc=True).isoformat()
            rows.append({"Asset": label, "Ticker": ticker, "Last": last, "1D": day, "1M": month, "AsOf": as_of})
        except Exception as error:
            warnings.append(f"{ticker}: {error}")
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS), warnings


def weekly_market_snapshot() -> tuple[pd.DataFrame, list[str]]:
    """Return exact one-week and one-month moves for the Sunday report."""
    configure_tls()
    rows: list[dict[str, object]] = []
    warnings: list[str] = []
    for label, ticker in WATCHLIST.items():
        try:
            encoded = requests.utils.quote(ticker, safe="")
            response = requests.get(
                f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}",
                params={"range": "3mo", "interval": "1d", "events": "div,splits"},
                headers={"User-Agent": "Mozilla/5.0 InvestorOS/1.0"}, timeout=20,
            )
            response.raise_for_status()
            result = response.json()["chart"]["result"][0]
            closes = [value for value in result["indicators"]["quote"][0]["close"] if value is not None]
            if len(closes) < 22:
                warnings.append(f"{ticker}: insufficient history.")
                continue
            last = float(closes[-1])
            rows.append({
                "Asset": label,
                "Ticker": ticker,
                "WeekStart": float(closes[-6]),
                "Last": last,
                "1W": float(last / closes[-6] - 1),
                "1M": float(last / closes[-22] - 1),
                "AsOf": pd.to_datetime(result["timestamp"][-1], unit="s", utc=True).isoformat(),
            })
        except Exception as error:
            warnings.append(f"{ticker}: {error}")
    return pd.DataFrame(rows, columns=WEEKLY_SNAPSHOT_COLUMNS), warnings


def classify_regime(snapshot: pd.DataFrame) -> Regime:
    if snapshot.empty:
        return Regime("No signal", "Market data is unavailable; do not infer a regime.")
    change = snapshot.set_index("Asset")["1M"]
    qqq = change.get("Nasdaq 100")
    spy = change.get("S&P 500")
    hyg = change.get("High yield credit")
    tlt = change.get("Long bonds")
    dollar = change.get("US dollar")
    required = [qqq, spy, hyg, tlt, dollar]
    if any(pd.isna(value) for value in required):
        return Regime("Partial signal", "Core risk, rates, credit, and dollar proxies are incomplete.")
    if qqq > 0 and spy > 0 and hyg > 0 and dollar <= 0:
        return Regime("Risk-on", "Equities and credit are advancing while the dollar is not tightening conditions.")
    if qqq < 0 and spy < 0 and hyg < 0 and (tlt > 0 or dollar > 0):
        return Regime("Risk-off", "Equities and credit are weakening with a defensive rates or dollar confirmation.")
    return Regime("Mixed", "Cross-asset signals disagree; avoid turning one move into a broad macro thesis.")


def rotation_table(snapshot: pd.DataFrame) -> pd.DataFrame:
    if snapshot.empty or "Asset" not in snapshot:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    sectors = snapshot[snapshot["Asset"].isin(["Semiconductors", "Technology", "Financials", "Energy", "Health care"])].copy()
    return sectors.sort_values("1M", ascending=False)
