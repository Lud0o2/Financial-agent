"""Generate and optionally deliver the deep Sunday Investor OS macro report."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import shutil

from dotenv import load_dotenv

from macro import weekly_market_snapshot
from macro_data import FRED_SERIES, fred_history
from network import configure_tls
from news import market_news
from telegram_alert import configured as telegram_configured, send


REPORTS_DIR = Path(__file__).resolve().parent / "data" / "weekly-reports"
DEFAULT_TRADING_COACH_DIR = Path(__file__).resolve().parents[2] / "trading coach agent"
INVESTOR_PORTFOLIO_SOURCE = Path(__file__).resolve().parents[1] / "investor-os" / "financials" / "portfolio.md"

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

USER_SUMMARY_PROMPT = """Create a concise English executive summary from the supplied weekly macro
report. Use ONLY facts, figures, interpretations, qualifications, and thresholds already present in the
report. Do not add facts or personalized trade advice. Target 350-500 words and stay below 3,800
characters so the complete text fits in one Telegram message.

Use exactly this editorial structure:
### Weekly Macro Summary — [week dates]
[One short paragraph naming the market regime, primary driver, and main cross-asset caveat.]

**Key moves:**
* [Asset]: **[weekly move]**
[Include only the 6-9 most decision-relevant moves.]

### 🟢 What is bullish
[Two compact paragraphs with exact supporting figures and the implied transmission mechanism.]

### 🟠 What warrants caution
[One or two compact paragraphs explaining the most important divergence or missing confirmation.]

### Next week
[State the base case in bold, then one compact bullish-confirmation paragraph and one compact bearish-
invalidation paragraph using exact thresholds when the source report provides them.]

**In one sentence:** [A direct regime conclusion with the main driver and the main caveat.]

Omit detailed chronology, exhaustive source notes, minor headlines, repeated caveats, disclaimers, and
generic commentary. If the source lacks an exact threshold, do not invent one."""


def _trading_coach_destination() -> Path | None:
    configured = os.getenv("TRADING_COACH_WORKSPACE")
    workspace = Path(configured).expanduser() if configured else DEFAULT_TRADING_COACH_DIR
    if not workspace.is_dir():
        return None
    return workspace / "Weekly_Macro_Report.md"


def _copy_to_trading_coach(report_path: Path) -> list[Path]:
    destination = _trading_coach_destination()
    if destination is None:
        return []
    shutil.copy2(report_path, destination)
    copied = [destination]
    if INVESTOR_PORTFOLIO_SOURCE.is_file():
        portfolio_destination = destination.parent / "Investor_OS_Portfolio_Snapshot.md"
        shutil.copy2(INVESTOR_PORTFOLIO_SOURCE, portfolio_destination)
        copied.append(portfolio_destination)
    return copied


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


def _summarize_for_user(client, model: str, report: str) -> str:
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": USER_SUMMARY_PROMPT},
            {"role": "user", "content": report},
        ],
        max_output_tokens=2500,
        text={"verbosity": "low"},
    )
    summary = response.output_text.strip()
    if not summary:
        raise RuntimeError("OpenAI returned an empty weekly user summary.")
    if len(summary) > 3800 or len(summary.split()) > 650:
        compression = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Compress this English weekly macro summary to 300-450 words and at most 3,500 "
                        "characters. Preserve the heading, key moves, bullish evidence, caution, next-week "
                        "confirmation/invalidation thresholds, and one-sentence conclusion. Remove only "
                        "secondary detail and repetition. Do not add facts. Return only the summary."
                    ),
                },
                {"role": "user", "content": summary},
            ],
            max_output_tokens=2200,
            text={"verbosity": "low"},
        )
        summary = compression.output_text.strip()
    if not summary or len(summary) > 3800 or len(summary.split()) > 650:
        raise RuntimeError(
            f"Weekly user summary exceeded its delivery limit ({len(summary)} characters, "
            f"{len(summary.split())} words)."
        )
    return summary


def generate_user_summary(report: str) -> str:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the weekly user summary.")
    from openai import OpenAI

    configure_tls()
    client = OpenAI()
    model = os.getenv("OPENAI_WEEKLY_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6"))
    return _summarize_for_user(client, model, report)


def generate_report() -> tuple[str, str, list[str]]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required for the deep weekly report.")
    evidence, warnings = _evidence()
    from openai import OpenAI

    configure_tls()
    client = OpenAI()
    model = os.getenv("OPENAI_WEEKLY_MODEL", os.getenv("OPENAI_MODEL", "gpt-5.6"))
    response = client.responses.create(
        model=model,
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
    summary = _summarize_for_user(client, model, report)
    return report, summary, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-send", action="store_true", help="Generate locally without Telegram delivery.")
    parser.add_argument("--summary-from", type=Path, help="Create the user summary from an existing full report.")
    args = parser.parse_args()
    load_dotenv(Path(__file__).resolve().parent / ".env")
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.summary_from:
        report = args.summary_from.resolve().read_text(encoding="utf-8")
        summary = generate_user_summary(report)
        warnings: list[str] = []
        output = args.summary_from.resolve()
        trading_coach_copies: list[Path] = []
    else:
        report, summary, warnings = generate_report()
        output = REPORTS_DIR / f"{datetime.now():%Y-%m-%d}-weekly-macro-report.md"
        output.write_text(report + "\n", encoding="utf-8")
        trading_coach_copies = _copy_to_trading_coach(output)
    summary_output = REPORTS_DIR / f"{datetime.now():%Y-%m-%d}-weekly-summary.md"
    summary_output.write_text(summary + "\n", encoding="utf-8")
    for warning in warnings:
        print(f"WARNING: {warning}")
    if not args.summary_from:
        if not trading_coach_copies:
            print("WARNING: Trading Coach Agent workspace was not found; report handoff skipped.")
        else:
            for copied_path in trading_coach_copies:
                print(f"TRADING COACH COPY: {copied_path}")
    if args.no_send or not telegram_configured():
        print(f"WEEKLY REPORT SAVED: {output}")
        print(f"USER SUMMARY SAVED: {summary_output}. Telegram delivery skipped.")
        return 0
    send(summary)
    print(f"USER SUMMARY SENT: {summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
