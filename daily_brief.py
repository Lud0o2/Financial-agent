"""Generate and optionally deliver the weekday Investor OS macro brief."""

from __future__ import annotations

from datetime import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
import pandas as pd

from charts import select_charts
from macro import market_snapshot
from macro_data import fred_snapshot
from market_analysis import analyze_market, telegram_report
from news import headline_read, market_news
from network import configure_tls
from telegram_alert import configured as telegram_configured, send, send_photo


BRIEFS_DIR = Path(__file__).resolve().parent / "data" / "briefs"


def _market_lines(snapshot: pd.DataFrame) -> str:
    return "\n".join(
        f"- {row['Asset']} ({row['Ticker']}): 1D {row['1D']:.1%}; 1M {row['1M']:.1%}"
        for _, row in snapshot.iterrows()
    )


def _legacy_fallback_brief(snapshot: pd.DataFrame, headlines: list[dict[str, str]]) -> str:
    read = headline_read(headlines)
    macro = fred_snapshot()
    horizons = horizon_map(macro)
    score = risk_score(macro)
    today_up = max(40, min(60, int(read["today_up"]) + score))
    week_up = max(40, min(60, int(read["week_up"]) + score))
    label = "Bullish" if today_up >= 54 else "Bearish" if today_up <= 46 else "Mixed"
    key_news = [item for item in headlines if item["topic"] == "Big market news"][:3] or headlines[:3]
    calendar = [item for item in headlines if item["topic"] == "Today calendar"][:2]
    big_money = [item for item in headlines if item["topic"] == "Big money"][:2]
    retail = [item for item in headlines if item["topic"] == "Retail feeling"][:1]
    sectors = [item for item in headlines if item["topic"] == "Sectors"][:2]
    liquidity = [item for item in headlines if item["topic"] == "Liquidity"][:1]
    earnings = [item for item in headlines if item["topic"] == "Earnings"][:2]
    breadth = [item for item in headlines if item["topic"] == "Breadth and options"][:1]
    mid_term = [item for item in headlines if item["topic"] == "Mid term"][:1]
    long_term = [item for item in headlines if item["topic"] == "Long term"][:1]
    advice = (
        "Do not force a trade. Wait for the first clear move after the open, then only act if your stop and thesis are already written."
        if label == "Mixed"
        else "Stay patient. If you trade, keep size small and use a hard stop. Do not chase the first move."
    )
    return "\n".join([
        f"📈 MARKET UPDATE — {datetime.now():%a %d %b}",
        "",
        "BIGGEST CATALYST",
        *[f"• {item['title']}" for item in key_news],
        "",
        "TODAY'S BIG EVENTS",
        *[f"• {item['title']}" for item in calendar],
        "",
        "SHORT TERM: RISK TODAY",
        *[f"• {line}" for line in horizons["Short term"]],
        *[f"• {item['title']}" for item in big_money],
        "",
        "MID TERM: NEXT FEW MONTHS",
        *[f"• {line}" for line in horizons["Mid term"]],
        *[f"• {item['title']}" for item in mid_term],
        "",
        "LONG TERM: LIQUIDITY",
        *[f"• {line}" for line in horizons["Long term"]],
        *[f"• {item['title']}" for item in liquidity],
        *[f"• {item['title']}" for item in long_term],
        "",
        "EARNINGS + SECTORS",
        *[f"• {item['title']}" for item in earnings],
        *[f"• {item['title']}" for item in retail],
        *[f"• {item['title']}" for item in sectors],
        *[f"• {item['title']}" for item in breadth],
        "",
        "MARKET FEELING",
        f"Good news: {read['positive']} | Bad news: {read['negative']}",
        f"Today: {today_up}% up / {100 - today_up}% down",
        f"This week: {week_up}% up / {100 - week_up}% down",
        "",
        "WHAT TO WATCH",
        "• Rising Treasury yield, high-yield stress, or market fear: this is bad for risk trades.",
        "• Falling yield and fear, plus tight credit: this helps risk trades.",
        "",
        "WHAT TO DO",
        advice,
        "",
        f"FINAL READ: {label.upper()} — simple news + Treasury + credit + fear check, not a promise.",
    ])


AI_SYSTEM_PROMPT = """You are the evidence-led analyst for Investor OS. Produce a very short Telegram
market brief using ONLY the supplied evidence. Never invent a fact, price, catalyst, consensus,
probability, support level, or causal claim. Separate OBSERVED FACTS from ANALYSIS/IMPLICATIONS.
Explain the transmission mechanism: what changed -> why markets care -> which assets are helped or
hurt -> what would confirm or invalidate the read. Treat news headlines as claims, not verified facts;
name their publisher and time. Mention disagreement across assets. Do not turn a tactical idea into a
core investment. Never recommend leverage without entry, hard stop, invalidation and >=2:1 reward/risk.
If evidence is insufficient, say NO TRADE / INSUFFICIENT DATA. Keep the entire answer under 2,000
characters and include no more than three material headlines. Use these exact compact sections:
MARKET VERDICT; OBSERVED DATA; WHAT CHANGED; DECISION FRAME; NEXT CONFIRMATION. Use bullets,
one sentence per bullet, and no markdown tables, preamble, recap, or generic market commentary."""


def _evidence(snapshot: pd.DataFrame, macro: dict, headlines: list[dict[str, str]]) -> str:
    prices = snapshot.to_dict(orient="records") if not snapshot.empty else []
    news = [{key: item.get(key, "") for key in ("topic", "title", "source", "published", "link")} for item in headlines]
    import json
    return json.dumps({"generated_at": datetime.now().astimezone().isoformat(), "market_prices": prices,
                       "macro_series": macro, "news_headlines": news}, ensure_ascii=False, default=str)


def _ai_brief(snapshot: pd.DataFrame, macro: dict, headlines: list[dict[str, str]]) -> str:
    if os.getenv("OPENAI_DAILY_BRIEF_ENABLED", "false").lower() != "true" or not os.getenv("OPENAI_API_KEY"):
        return telegram_report(analyze_market(headlines))
    from openai import OpenAI
    configure_tls()
    response = OpenAI().responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        input=[
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": "Create today's brief from this evidence JSON:\n" + _evidence(snapshot, macro, headlines)},
        ],
    )
    text = response.output_text.strip()
    if not text:
        raise RuntimeError("OpenAI returned an empty daily brief.")
    return text[:2000]


def _grounded_fallback(snapshot: pd.DataFrame, macro: dict, headlines: list[dict[str, str]]) -> str:
    """Concrete non-AI brief used only when the configured AI call is unavailable."""
    analysis = analyze_market(headlines)
    movers = snapshot.reindex(snapshot["1D"].abs().sort_values(ascending=False).index).head(6)
    price_lines = [
        f"• {row.Asset} ({row.Ticker}): {row.Last:,.2f} | 1D {row['1D']:+.2%} | 1M {row['1M']:+.2%} | {str(row.AsOf)[:10]}"
        for _, row in movers.iterrows()
    ]
    news_lines = [
        f"• {item['title']} — {item.get('source', 'Unknown source')} ({item.get('published', '')[:16]})"
        for item in headlines[:5]
    ]
    macro_lines = []
    for name in ("US 2Y Treasury", "US 10Y Treasury", "High-yield stress", "Market fear", "Inflation expectation"):
        item = macro.get(name)
        if item:
            macro_lines.append(f"• {name}: {float(item['value']):.2f}; change {float(item['change']):+.2f}; as of {item.get('as_of', 'unknown')}")
    return "\n".join([
        f"MARKET VERDICT — {analysis.regime}", analysis.regime_reason, "",
        "OBSERVED DATA", *price_lines, *macro_lines, "",
        "REAL NEWS (HEADLINE CLAIMS, NOT INDEPENDENTLY VERIFIED)", *news_lines, "",
        "WHAT IT IMPLIES",
        "• Falling yields with stable/tighter credit spreads supports duration assets; rising yields or widening spreads invalidates that read.",
        "• Equity strength without credit confirmation is fragile. Broad equity, small-cap and high-yield participation would strengthen risk-on evidence.",
        "• Liquidity helps risk assets only when earnings and credit do not deteriorate; it is context, not a timing signal.", "",
        "DECISION FRAME",
        "• NO TRADE from this brief alone. Tactical capital needs a live entry, hard stop, invalidation, catalyst and at least 2:1 reward/risk.",
        "• Core capital needs valuation, company fundamentals and earnings-revision evidence not present in this feed.", "",
        "NEXT CONFIRMATION",
        "• Check the next scheduled macro release against consensus, then watch the 10Y yield, high-yield spread and equity breadth reaction.",
        "• AI synthesis unavailable; this is the evidence-led fallback.",
    ])[:3900]


def main() -> int:
    load_dotenv(Path(__file__).resolve().parent / ".env")
    snapshot, market_warnings = market_snapshot()
    macro = fred_snapshot()
    headlines, news_warnings = market_news()
    if len(headlines) < 4:
        print("SKIPPED: news snapshot is incomplete. No notification sent.")
        for warning in news_warnings:
            print(warning)
        return 2
    if snapshot.empty or len(macro) < 5:
        print("SKIPPED: market or macro evidence is incomplete. No notification sent.")
        for warning in market_warnings + news_warnings:
            print(warning)
        return 2
    try:
        brief = _ai_brief(snapshot, macro, headlines)
    except Exception as error:
        print(f"AI BRIEF FAILED: {error}. Sending evidence-led fallback.")
        brief = _grounded_fallback(snapshot, macro, headlines)
    brief = brief[:2000]
    BRIEFS_DIR.mkdir(parents=True, exist_ok=True)
    output = BRIEFS_DIR / f"{datetime.now():%Y-%m-%d}.md"
    output.write_text(brief + "\n", encoding="utf-8")
    if not telegram_configured():
        print(f"BRIEF SAVED: {output}. Telegram is not configured, so nothing was sent.")
        return 0
    send(brief)
    for chart, caption in select_charts():
        send_photo(chart, caption)
    print(f"SENT: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
