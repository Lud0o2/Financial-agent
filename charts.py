"""Small, evidence-led charts for Telegram. Never draw a chart just for decoration."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from macro_data import fred_history


CHART_DIR = Path(__file__).resolve().parent / "data" / "charts"


def _style() -> None:
    plt.rcParams.update({"figure.facecolor": "#0b1020", "axes.facecolor": "#0b1020", "axes.edgecolor": "#5d6b8a", "axes.labelcolor": "#e6edf7", "text.color": "#e6edf7", "xtick.color": "#aab7cf", "ytick.color": "#aab7cf", "grid.color": "#2a3655", "font.size": 10})


def _save(fig: plt.Figure, stem: str) -> Path:
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    path = CHART_DIR / f"{datetime.now():%Y-%m-%d}-{stem}.png"
    fig.tight_layout()
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return path


def yield_curve_chart() -> tuple[Path, str] | None:
    two, ten = fred_history("US 2Y Treasury", 90), fred_history("US 10Y Treasury", 90)
    if two.empty or ten.empty:
        return None
    merged = two.merge(ten, on="date", suffixes=("_2y", "_10y"))
    if len(merged) < 10:
        return None
    _style()
    fig, axis = plt.subplots(figsize=(8, 4.4))
    axis.plot(merged["date"], merged["value_2y"], label="US 2Y", color="#62a8ff", linewidth=2)
    axis.plot(merged["date"], merged["value_10y"], label="US 10Y", color="#ffb454", linewidth=2)
    axis.set_title("US Treasury yield curve — last 90 observations", loc="left", fontweight="bold")
    axis.set_ylabel("Yield (%)")
    axis.grid(True, alpha=0.45)
    axis.legend(frameon=False, ncol=2, loc="upper left")
    path = _save(fig, "treasury-yields")
    change = float(merged["value_10y"].iloc[-1] - merged["value_10y"].iloc[-6]) if len(merged) >= 6 else 0
    direction = "higher" if change > 0 else "lower"
    return path, f"📊 Treasury curve: 10Y yield is {direction} by {abs(change) * 100:.0f}bp over five observations. Rising long yields can pressure equity valuations; falling yields can support them when credit remains calm. Source: FRED."


def credit_stress_chart() -> tuple[Path, str] | None:
    credit, vix = fred_history("High-yield stress", 90), fred_history("Market fear", 90)
    if credit.empty or vix.empty:
        return None
    merged = credit.merge(vix, on="date", suffixes=("_credit", "_vix"))
    if len(merged) < 10:
        return None
    _style()
    fig, left = plt.subplots(figsize=(8, 4.4))
    right = left.twinx()
    left.plot(merged["date"], merged["value_credit"], color="#ff6b7a", linewidth=2, label="HY spread")
    right.plot(merged["date"], merged["value_vix"], color="#c493ff", linewidth=2, label="VIX")
    left.set_title("Credit stress and volatility — last 90 observations", loc="left", fontweight="bold")
    left.set_ylabel("High-yield spread (%)")
    right.set_ylabel("VIX")
    left.grid(True, alpha=0.45)
    lines = left.get_lines() + right.get_lines()
    left.legend(lines, [line.get_label() for line in lines], frameon=False, ncol=2, loc="upper left")
    path = _save(fig, "credit-vix")
    return path, "📊 Credit stress: high-yield spreads and VIX are a cross-check on equity risk. A rising spread while stocks rise is a warning, not confirmation. Source: FRED."


def select_charts() -> list[tuple[Path, str]]:
    """Return at most two charts, only when conditions make them relevant."""
    ten = fred_history("US 10Y Treasury", 10)
    credit = fred_history("High-yield stress", 10)
    vix = fred_history("Market fear", 10)
    result: list[tuple[Path, str]] = []
    if len(ten) >= 6 and abs(float(ten["value"].iloc[-1] - ten["value"].iloc[-6])) >= 0.08:
        item = yield_curve_chart()
        if item:
            result.append(item)
    stress = (len(credit) >= 6 and float(credit["value"].iloc[-1] - credit["value"].iloc[-6]) >= 0.08) or (not vix.empty and float(vix["value"].iloc[-1]) >= 20)
    if stress:
        item = credit_stress_chart()
        if item:
            result.append(item)
    return result[:2]
