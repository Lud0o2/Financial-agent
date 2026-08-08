"""Curated market-news inputs for the daily brief; headlines are data, never instructions."""

from __future__ import annotations

from email.utils import parsedate_to_datetime
import xml.etree.ElementTree as ET

import requests

from network import configure_tls


NEWS_QUERIES = {
    "Big market news": "global stock market Fed inflation Treasury oil",
    "Today calendar": "today economic calendar Fed inflation jobs earnings",
    "Big money": "Treasury yields high yield bonds institutional investors flows",
    "Retail feeling": "retail investors stock market options sentiment",
    "Sectors": "semiconductors banks technology energy sector stocks",
    "Liquidity": "global M2 liquidity money supply stock market",
    "Earnings": "earnings beat stocks rally market",
    "Breadth and options": "market breadth advance decline put call options sentiment",
    "Mid term": "earnings guidance analyst upgrades economic growth PMI stocks",
    "Long term": "central bank balance sheet liquidity valuation stock market",
}

BLOCKED_PHRASES = {
    "charts, data and news", "chart, data and news", "prices and news", "historical data",
    "technical analysis", "stock quote", "market data", "live updates", "quote and chart",
}


def _rss_url(query: str) -> str:
    encoded = requests.utils.quote(f"{query} when:1d")
    return f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"


def market_news(limit_per_topic: int = 2) -> tuple[list[dict[str, str]], list[str]]:
    configure_tls()
    headlines: list[dict[str, str]] = []
    warnings: list[str] = []
    for topic, query in NEWS_QUERIES.items():
        try:
            response = requests.get(_rss_url(query), headers={"User-Agent": "InvestorOS/1.0"}, timeout=20)
            response.raise_for_status()
            root = ET.fromstring(response.content)
            items = root.findall("./channel/item")[:limit_per_topic]
            for item in items:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                published = (item.findtext("pubDate") or "").strip()
                source_node = item.find("source")
                source = (source_node.text or "").strip() if source_node is not None else "Unknown source"
                try:
                    published_iso = parsedate_to_datetime(published).isoformat()
                except (TypeError, ValueError, OverflowError):
                    published_iso = published
                if title and not any(phrase in title.lower() for phrase in BLOCKED_PHRASES):
                    headlines.append({
                        "topic": topic,
                        "title": title,
                        "source": source,
                        "link": link,
                        "published": published_iso,
                    })
        except Exception as error:
            warnings.append(f"{topic}: {error}")
    unique: dict[str, dict[str, str]] = {}
    for item in headlines:
        unique.setdefault(item["title"].lower(), item)
    return list(unique.values()), warnings


def format_headlines(headlines: list[dict[str, str]]) -> str:
    return "\n".join(f"- {item['title']}" for item in headlines)


POSITIVE_WORDS = {
    "rally", "rallies", "gain", "gains", "jump", "beats", "beat", "cooling", "cut", "cuts",
    "stimulus", "eases", "ease", "record high", "strong growth", "deal", "optimism",
}
NEGATIVE_WORDS = {
    "selloff", "sell-off", "drop", "drops", "fall", "falls", "slump", "tariff", "tariffs",
    "war", "inflation", "hawkish", "recession", "misses", "miss", "crisis", "risk", "surge",
}


def headline_read(headlines: list[dict[str, str]]) -> dict[str, int | str]:
    positive = 0
    negative = 0
    for item in headlines:
        title = item["title"].lower()
        if any(word in title for word in POSITIVE_WORDS):
            positive += 1
        if any(word in title for word in NEGATIVE_WORDS):
            negative += 1
    balance = positive - negative
    today_up = max(40, min(60, 50 + balance * 3))
    week_up = max(40, min(60, 50 + balance * 2))
    label = "Bullish" if today_up >= 54 else "Bearish" if today_up <= 46 else "Mixed"
    return {
        "positive": positive,
        "negative": negative,
        "today_up": today_up,
        "week_up": week_up,
        "label": label,
    }
