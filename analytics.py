"""Portfolio-level calculations and deterministic risk flags."""

from __future__ import annotations

import pandas as pd


def position_weights(positions: pd.DataFrame) -> pd.DataFrame:
    result = positions.copy()
    values = result["Marked value (EUR)"].fillna(result["Remaining cost basis (EUR)"])
    total = values.sum()
    result["Portfolio value (EUR)"] = values
    result["Weight"] = values / total if total else 0
    return result.sort_values("Weight", ascending=False)


def risk_flags(positions: pd.DataFrame) -> list[str]:
    weighted = position_weights(positions)
    flags: list[str] = []
    if weighted.empty:
        return ["No open positions were found in the portfolio snapshot."]

    largest = weighted.iloc[0]
    if largest["Weight"] > 0.25:
        flags.append(f"Concentration: {largest['Ticker']} is {largest['Weight']:.1%} of marked invested capital.")

    missing_marks = weighted[weighted["Marked value (EUR)"].isna()]
    if not missing_marks.empty:
        tickers = ", ".join(missing_marks["Ticker"].astype(str))
        flags.append(f"Data integrity: missing marked values for {tickers}; totals treat those positions at cost.")

    worst = weighted.loc[weighted["Unrealised P&L (EUR)"].idxmin()]
    if pd.notna(worst["Unrealised P&L (EUR)"]) and worst["Unrealised P&L (EUR)"] < 0:
        flags.append(f"Thesis check: {worst['Ticker']} has the largest recorded unrealised loss ({worst['Unrealised P&L (EUR)']:,.2f} EUR).")

    return flags


def morning_brief(positions: pd.DataFrame, totals: dict[str, float | None], source_date: str) -> str:
    weighted = position_weights(positions)
    net_gain = totals.get("Net gain after fees")
    return_rate = totals.get("Reported total return")
    cash = totals.get("Uninvested cash")
    invested = totals.get("Open-position cost basis")
    lines = [
        "## Morning brief",
        f"**Portfolio data:** recorded through {source_date}; this is not a live mark.",
        f"**Open cost basis:** EUR {invested:,.2f}" if invested is not None else "**Open cost basis:** unavailable.",
        f"**Cash recorded:** EUR {cash:,.2f}" if cash is not None else "**Cash recorded:** unavailable.",
        f"**Net gain after fees:** EUR {net_gain:,.2f} ({return_rate:.1f}% reported total return)." if net_gain is not None and return_rate is not None else "**Net gain after fees:** unavailable.",
        "\n### Positioning",
    ]
    for _, row in weighted.head(3).iterrows():
        unrealised = row["Unrealised P&L (EUR)"]
        unrealised = 0 if pd.isna(unrealised) else unrealised
        lines.append(f"- {row['Ticker']}: {row['Weight']:.1%} of marked invested capital; recorded unrealised P&L EUR {unrealised:,.2f}.")
    lines.extend(["\n### Risk controls", *[f"- {flag}" for flag in risk_flags(positions)]])
    lines.append("\n**Next action:** refresh broker prices and review the thesis, stop, and sizing for the largest loss before considering any new deployment.")
    return "\n".join(lines)
