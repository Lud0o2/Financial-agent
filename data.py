"""Read the Investor OS markdown files without making them a second source of truth."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OS_DIR = ROOT / "investor-os"
FINANCIALS_DIR = OS_DIR / "financials"
PORTFOLIO_FILE = FINANCIALS_DIR / "portfolio.md"
ONE_PAGER_FILE = OS_DIR / "investor-one-pager.md"
MEMORY_FILE = OS_DIR / "memory.md"
PNL_FILE = FINANCIALS_DIR / "pnl-summary.md"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _parse_table(markdown: str) -> pd.DataFrame:
    rows = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        return pd.DataFrame()
    values = [[cell.strip() for cell in row.strip("|").split("|")] for row in rows]
    header = values[0]
    body = [row for row in values[2:] if len(row) == len(header)]
    return pd.DataFrame(body, columns=header)


def _money(value: object) -> float | None:
    text = str(value).replace("**", "").strip()
    if not text or "TODO" in text or text == "-":
        return None
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "").replace("*", "").replace("%", "")
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def load_open_positions() -> pd.DataFrame:
    text = read_text(PORTFOLIO_FILE)
    table = _parse_table(_section(text, "Open positions"))
    if table.empty:
        return table
    table = table[~table["Holding"].str.contains("Open positions total", na=False)].copy()
    numeric_columns = [
        "Quantity",
        "Remaining cost basis (EUR)",
        "Unrealised P&L (EUR)",
        "Marked value (EUR)",
        "Realised gains (EUR)",
        "Total gain after fees (EUR)",
    ]
    for column in numeric_columns:
        table[column] = table[column].map(_money)
    table["Quantity"] = pd.to_numeric(table["Quantity"], errors="coerce")
    return table


def load_closed_positions() -> pd.DataFrame:
    text = read_text(PORTFOLIO_FILE)
    table = _parse_table(_section(text, "Closed positions with recorded cumulative gains"))
    for column in ["Total invested (EUR)", "Realised gains (EUR)", "Total gain after fees (EUR)"]:
        if column in table:
            table[column] = table[column].map(_money)
    return table


def load_totals() -> dict[str, float | None]:
    table = _parse_table(_section(read_text(PORTFOLIO_FILE), "Portfolio totals"))
    if table.empty:
        return {}
    return {str(row["Measure"]): _money(row["EUR"]) for _, row in table.iterrows()}


def build_context() -> str:
    parts = []
    for label, path in [
        ("Investor one-pager", ONE_PAGER_FILE),
        ("Memory", MEMORY_FILE),
        ("P&L summary", PNL_FILE),
        ("Portfolio snapshot", PORTFOLIO_FILE),
    ]:
        parts.append(f"# {label}\n{read_text(path)}")
    return "\n\n".join(parts)


def source_status() -> str:
    text = read_text(PORTFOLIO_FILE)
    match = re.search(r"Position data recorded through:\*\* (\d{4}-\d{2}-\d{2})", text)
    return match.group(1) if match else "unknown"
