"""Telegram delivery. Keep credentials in .env; never in source control."""

from __future__ import annotations

import os
from pathlib import Path

import requests

from network import configure_tls


def configured() -> bool:
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def send(text: str) -> None:
    if not configured():
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set before delivery.")
    configure_tls()
    response = requests.post(
        f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
        json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text},
        timeout=20,
    )
    response.raise_for_status()


def send_photo(path: Path, caption: str) -> None:
    """Deliver one compact chart. Telegram retains the image for the user."""
    if not configured():
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set before delivery.")
    configure_tls()
    with path.open("rb") as image:
        response = requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendPhoto",
            data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption},
            files={"photo": image},
            timeout=30,
        )
    response.raise_for_status()


def send_document(path: Path, caption: str) -> None:
    """Deliver a long-form report as a Telegram document."""
    if not configured():
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set before delivery.")
    configure_tls()
    with path.open("rb") as document:
        response = requests.post(
            f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendDocument",
            data={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "caption": caption},
            files={"document": (path.name, document, "text/markdown")},
            timeout=60,
        )
    response.raise_for_status()
