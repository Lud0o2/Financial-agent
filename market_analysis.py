"""Structured, evidence-led market analysis built from public data proxies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from macro_data import fred_snapshot, horizon_map


@dataclass(frozen=True)
class MarketAnalysis:
    timestamp: str
    regime: str
    regime_reason: str
    score: int
    components: dict[str, int]
    facts: dict[str, list[str]]
    interpretation: list[str]
    risks: list[str]
    scenarios: list[str]
    setups: list[str]
    long_term: list[str]


def _number(snapshot: dict[str, dict[str, float | str]], name: str, field: str = "change") -> float | None:
    value = snapshot.get(name, {}).get(field)
    return float(value) if value is not None else None


def _regime(snapshot: dict[str, dict[str, float | str]]) -> tuple[str, str]:
    ten_year = _number(snapshot, "US 10Y Treasury")
    credit = _number(snapshot, "High-yield stress")
    vix = _number(snapshot, "Market fear", "value")
    conditions = _number(snapshot, "Financial conditions")
    money = _number(snapshot, "US M2 money supply")
    if (credit is not None and credit > 0.12) or (vix is not None and vix >= 25):
        return "Risk-off / financial-stress watch", "Credit stress or volatility is elevated; preserving capital matters more than chasing upside."
    if conditions is not None and conditions < 0 and money is not None and money > 0 and ten_year is not None and ten_year <= 0:
        return "Disinflationary risk-on", "Conditions are easing, liquidity is improving, and yields are not rising into risk assets."
    if ten_year is not None and ten_year > 0.08:
        return "Rate-pressure / mixed risk", "Long yields are rising enough to pressure equity valuations even if growth news is positive."
    return "Mixed / wait for confirmation", "Rates, credit, volatility, and liquidity do not yet give a single high-conviction message."


def _components(snapshot: dict[str, dict[str, float | str]]) -> dict[str, int]:
    ten_year = _number(snapshot, "US 10Y Treasury")
    credit = _number(snapshot, "High-yield stress")
    vix = _number(snapshot, "Market fear")
    conditions = _number(snapshot, "Financial conditions")
    m2 = _number(snapshot, "US M2 money supply")
    fed = _number(snapshot, "Fed balance sheet")
    macro = 6 if ten_year is not None and ten_year <= 0 else -6 if ten_year is not None else 0
    credit_score = (15 if credit is not None and credit <= 0 else -15 if credit is not None else 0) + (8 if vix is not None and vix <= 0 else -8 if vix is not None else 0)
    liquidity = (8 if m2 is not None and m2 > 0 else -8 if m2 is not None else 0) + (4 if fed is not None and fed > 0 else -4 if fed is not None else 0) + (6 if conditions is not None and conditions < 0 else -6 if conditions is not None else 0)
    return {"Macro/rates": macro, "Liquidity": liquidity, "Credit/volatility": credit_score, "Earnings": 0, "Valuation": 0, "Breadth": 0, "Positioning": 0, "Technicals": 0}


def _liquidity_label(snapshot: dict[str, dict[str, float | str]]) -> str:
    points = 0
    for name in ("US M2 money supply", "Fed balance sheet"):
        change = _number(snapshot, name)
        if change is not None:
            points += 1 if change > 0 else -1
    conditions = _number(snapshot, "Financial conditions")
    if conditions is not None:
        points += 1 if conditions < 0 else -1
    return "EXPANDING" if points >= 2 else "CONTRACTING" if points <= -2 else "NEUTRAL"


def analyze_market(headlines: list[dict[str, str]]) -> MarketAnalysis:
    snapshot = fred_snapshot()
    regime, reason = _regime(snapshot)
    components = _components(snapshot)
    score = max(-100, min(100, sum(components.values())))
    horizons = horizon_map(snapshot)
    liquidity = _liquidity_label(snapshot)
    key_news = [item["title"] for item in headlines if item["topic"] in {"Big market news", "Today calendar"}][:3]
    earnings_news = [item["title"] for item in headlines if item["topic"] in {"Earnings", "Mid term"}][:2]
    interpretation = [
        "Fact: the regime is based on rates, credit, volatility, and liquidity proxies — not headline counts.",
        f"Liquidity read: {liquidity}. This matters most for growth stocks, small caps, crypto, and gold when credit stays calm.",
        "Weak data can help through lower yields, but becomes bearish when credit spreads widen and earnings expectations fall.",
    ]
    risks = [
        "HIGH: a sharp rise in 10Y yields or high-yield spreads would challenge risk assets.",
        "MEDIUM: earnings, valuation, breadth, options positioning, and ETF-flow data are not connected; do not assume they confirm the macro signal.",
    ]
    bull = 40 if score >= 10 else 25
    bear = 25 if score >= 10 else 40
    base = 100 - bull - bear
    scenarios = [
        f"Bull case — {bull}%: yields stay contained, credit remains calm, and earnings news confirms demand.",
        f"Base case — {base}%: range or selective leadership while the next macro catalyst resets expectations.",
        f"Bear case — {bear}%: yields or credit stress rise, turning weak growth data into an earnings-risk story.",
    ]
    setups = ["NO TRADE — exact index price, support/resistance, breadth, and options data are not available. Do not use leverage without a defined entry, stop, catalyst, and at least 2:1 reward/risk."]
    long_term = ["WATCHLIST ONLY — forward valuation, earnings revisions, and company fundamentals are not connected. A great company is not automatically a good entry price."]
    facts = {
        "Short term": horizons["Short term"], "Medium term": horizons["Mid term"], "Long term": horizons["Long term"],
        "What matters": key_news or ["Data unavailable: no fresh, relevant catalyst headline."],
        "Earnings": earnings_news or ["Data unavailable: no fresh earnings/revision feed."],
    }
    return MarketAnalysis(datetime.now().strftime("%a %d %b %Y %H:%M local"), regime, reason, score, components, facts, interpretation, risks, scenarios, setups, long_term)


def telegram_report(analysis: MarketAnalysis) -> str:
    classification = "MODERATELY BULLISH" if analysis.score >= 15 else "MODERATELY BEARISH" if analysis.score <= -15 else "NEUTRAL / MIXED"
    component_lines = [f"{name}: {value:+d}" for name, value in analysis.components.items() if value]
    return "\n".join([
        f"📊 MARKET INTELLIGENCE — {analysis.timestamp}", "", "🌎 MARKET REGIME", f"{analysis.regime}: {analysis.regime_reason}", "",
        "🔥 WHAT ACTUALLY MATTERS TODAY", *[f"• {item}" for item in analysis.facts["What matters"]], "",
        "💵 MACRO / CREDIT / VOLATILITY", *[f"• {item}" for item in analysis.facts["Short term"]], "",
        "💧 LIQUIDITY + MEDIUM TERM", *[f"• {item}" for item in analysis.facts["Medium term"] + analysis.facts["Long term"]], "",
        "🧭 HOW TO READ IT", *[f"• {item}" for item in analysis.interpretation], "",
        "📈 EARNINGS + INTERNALS", *[f"• {item}" for item in analysis.facts["Earnings"]], "• Breadth, valuation, positioning, ETF flows: Data unavailable (no specialist feed connected).", "",
        "⚠️ KEY RISKS", *[f"• {item}" for item in analysis.risks], "",
        "🎯 SHORT-TERM TRADING SETUPS", *[f"• {item}" for item in analysis.setups], "",
        "💼 LONG-TERM INVESTMENTS", *[f"• {item}" for item in analysis.long_term], "",
        "🔮 SCENARIOS", *[f"• {item}" for item in analysis.scenarios], "",
        "🗓 NEXT CATALYST", "• Data unavailable: a live economic-calendar and consensus-expectations feed is not connected.", "",
        "🏁 FINAL READ", f"Score: {analysis.score:+d} / 100 ({classification})", f"Components: {' | '.join(component_lines) or 'Data unavailable'}", "Facts and interpretations are separated above. Scenarios are subjective estimates, not guarantees.",
    ])
