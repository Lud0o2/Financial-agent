"""Optional OpenAI-backed analysis, grounded in the local Investor OS."""

from __future__ import annotations

import os

from data import build_context
from memory import recent_messages
from network import configure_tls


SYSTEM_PROMPT = """You are the user's personal investment strategist. Be probing, direct, and concise.
You frame decisions; you do not make them. The Investor One-Pager is authoritative. Name any rule
violated by a proposed action before discussing upside. Do not reclassify a failed tactical trade as
a core holding. Distinguish recorded facts from inference and point out stale or missing data."""


def is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def answer(question: str) -> str:
    if not is_configured():
        raise RuntimeError("OPENAI_API_KEY is not configured. Add it to .env to enable chat.")

    from openai import OpenAI

    configure_tls()
    history = recent_messages()
    client = OpenAI()
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6"),
        input=[
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{build_context()}"},
            *history,
            {"role": "user", "content": question},
        ],
    )
    return response.output_text
