"""Reliable public macro checks from FRED. These are risk gauges, not trade signals."""

from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

from network import configure_tls


FRED_SERIES = {
    "US 2Y Treasury": ("DGS2", "%"),
    "US 10Y Treasury": ("DGS10", "%"),
    "Yield curve": ("T10Y2Y", "%"),
    "High-yield stress": ("BAMLH0A0HYM2", "%"),
    "Market fear": ("VIXCLS", ""),
    "US M2 money supply": ("M2SL", "m2"),
    "Fed balance sheet": ("WALCL", "balance"),
    "Financial conditions": ("NFCI", "index"),
    "Inflation expectation": ("T5YIE", "%"),
}


def fred_history(label: str, periods: int = 90) -> pd.DataFrame:
    """Return recent observations for one configured FRED series.

    The caller must treat every returned series as a dated public-data proxy,
    not an intraday tradable quote.
    """
    if label not in FRED_SERIES:
        return pd.DataFrame(columns=["date", "value"])
    series, _ = FRED_SERIES[label]
    configure_tls()
    try:
        response = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}", timeout=20)
        response.raise_for_status()
        data = pd.read_csv(StringIO(response.text))
        data[series] = pd.to_numeric(data[series], errors="coerce")
        data = data.dropna(subset=[series]).tail(periods).rename(columns={"observation_date": "date", series: "value"})
        data["date"] = pd.to_datetime(data["date"])
        return data[["date", "value"]]
    except Exception:
        return pd.DataFrame(columns=["date", "value"])


def fred_snapshot() -> dict[str, dict[str, float | str]]:
    configure_tls()
    results: dict[str, dict[str, float | str]] = {}
    for label, (series, unit) in FRED_SERIES.items():
        try:
            data = fred_history(label, periods=10)
            values = data["value"]
            if len(values) >= 2:
                if unit in {"m2", "balance"}:
                    base = values.iloc[-5] if len(values) >= 5 else values.iloc[0]
                    change = float(values.iloc[-1] / base - 1) if base else 0.0
                else:
                    change = float(values.iloc[-1] - values.iloc[-2])
                results[label] = {
                    "value": float(values.iloc[-1]),
                    "change": change,
                    "unit": unit,
                    "as_of": data["date"].iloc[-1].date().isoformat(),
                }
        except Exception:
            continue
    return results


def risk_score(snapshot: dict[str, dict[str, float | str]]) -> int:
    score = 0
    treasury = snapshot.get("US 10Y Treasury")
    credit = snapshot.get("High-yield stress")
    fear = snapshot.get("Market fear")
    if treasury:
        score += -1 if float(treasury["change"]) > 0 else 1
    if credit:
        score += -2 if float(credit["change"]) > 0 else 2
    if fear:
        score += -1 if float(fear["change"]) > 0 else 1
    money = snapshot.get("US M2 money supply")
    if money:
        score += 1 if float(money["change"]) > 0 else -1
    conditions = snapshot.get("Financial conditions")
    if conditions:
        score += -1 if float(conditions["change"]) > 0 else 1
    return score


def format_macro(snapshot: dict[str, dict[str, float | str]]) -> list[str]:
    lines: list[str] = []
    for label, data in snapshot.items():
        value = float(data["value"])
        change = float(data["change"])
        if data["unit"] == "%":
            lines.append(f"• {label}: {value:.2f}% ({change * 100:+.0f} bp today)")
        elif data["unit"] == "m2":
            lines.append(f"• US M2 money supply: {change:+.1%} over about 4 weeks")
        elif data["unit"] == "balance":
            lines.append(f"• Fed balance sheet: {change:+.1%} over about 4 weeks")
        elif data["unit"] == "index":
            direction = "easier" if change < 0 else "tighter"
            lines.append(f"• Financial conditions: {direction} ({change:+.2f})")
        else:
            lines.append(f"• {label}: {value:.1f} ({change:+.1f} today)")
    return lines


def horizon_map(snapshot: dict[str, dict[str, float | str]]) -> dict[str, list[str]]:
    def line(name: str) -> str | None:
        data = snapshot.get(name)
        if not data:
            return None
        value, change, unit = float(data["value"]), float(data["change"]), data["unit"]
        if unit == "%":
            suffix = "bp today"
            delta = f"{change * 100:+.0f}"
            return f"{name}: {value:.2f}% ({delta} {suffix})"
        if unit in {"m2", "balance"}:
            return f"{name}: {change:+.1%} over about 4 weeks"
        if unit == "index":
            return f"{name}: {value:.2f} ({change:+.2f})"
        return f"{name}: {value:.1f} ({change:+.1f})"

    groups = {
        "Short term": ["US 2Y Treasury", "US 10Y Treasury", "High-yield stress", "Market fear"],
        "Mid term": ["Yield curve", "Financial conditions", "Inflation expectation"],
        "Long term": ["US M2 money supply", "Fed balance sheet", "Yield curve"],
    }
    return {label: [value for name in names if (value := line(name))] for label, names in groups.items()}
