"""Бункер сипаттамасы мен апат сценарийін кездейсоқ таңдау қызметі."""
import json
import os
import random

from config import DATA_DIR


def _load(filename: str) -> list[dict]:
    path = os.path.join(DATA_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_scenario() -> tuple[dict, dict]:
    """(bunker, disaster) жұбын кездейсоқ таңдайды."""
    bunkers = _load("bunker.json")
    disasters = _load("disasters.json")
    return random.choice(bunkers), random.choice(disasters)


def format_scenario_message(bunker: dict, disaster: dict) -> str:
    return (
        "🛡 <b>Бункер сипаттамасы</b>\n"
        f"<b>{bunker['title']}</b>\n"
        f"{bunker['description']}\n\n"
        "☣ <b>Апат сценарийі</b>\n"
        f"<b>{disaster['title']}</b>\n"
        f"{disaster['description']}"
    )
