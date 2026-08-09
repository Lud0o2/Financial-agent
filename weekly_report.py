"""Generate and optionally deliver the deep Sunday Investor OS macro report."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

from dotenv import load_dotenv

from macro import weekly_market_snapshot
from macro_data import FRED_SERIES, fred_history
from network import configure_tls
from news import market_news
from telegram_alert import configured as telegram_configured, send_document


REPORTS_DIR = Path(__file__).resolve().parent / "data" / "weekly-reports"

WEEKLY_SYSTEM_PROMPT = """You are the evidence-led weekly macro analyst for Investor OS.
Write a deep, standalone weekly report in English using ONLY the supplied evidence. The editorial
model is a professional macro research note: rebuild the map from first principles, rank changes by
importance, quantify them, explain transmission mechanisms, surface contradictions, and state what
would confirm or invalidate each interpretation. Never invent facts, consensus estimates,
probabilities, events, price levels, or causal claims. News items are publisher-attributed headline
claims, not independently verified facts. Explicitly label facts, inference, and missing evidence.

Use this exact architecture:
# Investor OS Weekly Macro Report
## Executive map
## 1. Opening baseline
## 2. The week's five most important changes
## 3. Rates, inflation, growth, and liquidity
## 4. Cross-asset dashboard
## 5. News chronology and transmission mechanisms
## 6. Where markets disagree
## 7. What the market may be pricing
## 8. Coming-week catalyst calendar
## 9. Bull, base, and bear scenarios
## 10. Known, unknown, inferred, and what would change the view
## Source notes and limitations

Requirements: aim for 3,000-5,000 words when the evidence supports it; use compact Markdown tables
for exact figures; date every observation; include a one-sentence takeaway after major sections; make
every scenario include confirmation and invalidation conditions; do not personalize a trade or give
investment instructions; close with an educational, non-advisory disclaimer. If the supplied evidence
does not establish an item such as an economic-calendar event or market-implied probability, say so
and give the exact evidence needed rather than filling the gap."""


def _macro_week() -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for label, (series_id, unit) in FRED_SERIES.items():
        history = fred_history(label, periods=35)
        if history.empty:
            continue
        latest = history.iloc[-1]
        cutoff = latest["date"] - timedelta(days=7)
        prior_rows = history[history["date"] <= cutoff]
        prior = prior_rows.iloc[-1] if not prior_rows.empty else history.iloc[0]
        start_value = float(prior["value"])
        end_value = float(latest["value"])
        output[label] = {
            "series_id": series_id,
            "unit": unit,
            "start_date": prior["date"].date().isoformat(),
            "start_value": start_value,
            "end_date": latest["date"].date().isoformat(),
            "end_value": end_value,
            "absolute_change": end_value - start_value,
            "percent_change": (end_value / start_value - 1) if start_value else None,
        }
    return output


def _evidence() -> tuple[str, list[str]]:
    market, market_warnings = weekly_market_snapshot()
    headlines, news_warnings = market_news(limit_per_topic=4, lookback_days=7)
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(),
        "period_note": "Latest five trading sessions and latest available weekly macro observations.",
        "cross_asset_week": market.to_dict(orient="records"),
        "macro_week": _macro_week(),
        "publisher_attributed_headline_claims": [
            {key: item.get(key, "") for key in ("topic", "title", "source", "published", "link")}
            for item in headlines
        ],
    }
    return json.dumps(payload, ensure_ascii=False, default=str), market_warnings + news_warnings


def generate_report() -> tuple[str, list[str]]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the deep weekly report.")
    evidence, warnings = _evidence()
    from openai import OpenAI

    configure_tls()
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_WEEKLY_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6")),
        input=[
            {"role": "system", "content": WEEKLY_SYSTEM_PROMPT},
            {"role": "user", "content": "Create this Sunday's report from the evidence JSON:\n" + evidence},
        ],
        max_output_tokens=16000,
        text={"verbosity": "high"},
    )
    report = response.output_text.strip()
    if not report:
        raise RuntimeError("OpenAI returned an empty weekly report.")
    return report, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-send", action="store_true", help="Generate locally without Telegram delivery.")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent / ".env")
    report, warnings = generate_report()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORTS_DIR / f"{datetime.now():%Y-%m-%d}-weekly-macro-report.md"
    output.write_text(report + "\n", encoding="utf-8")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if args.no_send or not telegram_configured():
        print(f"WEEKLY REPORT SAVED: {output}. Telegram delivery skipped.")
        return 0
    send_document(output, f"Investor OS weekly macro report - {datetime.now():%d %b %Y}")
    print(f"WEEKLY REPORT SENT: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
