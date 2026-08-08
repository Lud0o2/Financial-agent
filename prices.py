"""Optional price lookup. Prices are display-only and never overwrite the Investor OS."""

from __future__ import annotations

import pandas as pd


YAHOO_TICKERS = {
    "META.US": "META",
    "FISV.US": "FISV",
}


def live_prices(positions: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    try:
        import yfinance as yf
    except ImportError as error:
        return pd.DataFrame(), [f"Live pricing is unavailable: {error}. Install requirements first."]

    records: list[dict[str, object]] = []
    warnings: list[str] = []
    for _, position in positions.iterrows():
        source_ticker = position["Ticker"]
        ticker = YAHOO_TICKERS.get(source_ticker, source_ticker)
        if source_ticker == "XCS6.UK":
            warnings.append("XCS6.UK has no configured Yahoo Finance mapping; add one after confirming its exchange ticker.")
            continue
        try:
            history = yf.Ticker(ticker).history(period="5d", auto_adjust=False)
            if history.empty:
                warnings.append(f"{source_ticker}: no price returned.")
                continue
            close = float(history["Close"].iloc[-1])
            previous = float(history["Close"].iloc[-2]) if len(history) > 1 else close
            records.append({
                "Ticker": source_ticker,
                "Yahoo ticker": ticker,
                "Last close": close,
                "Day change": (close / previous - 1) if previous else None,
                "Currency": getattr(yf.Ticker(ticker).fast_info, "currency", "Unknown"),
            })
        except Exception as error:  # Provider availability should not break the dashboard.
            warnings.append(f"{source_ticker}: {error}")
    return pd.DataFrame(records), warnings
