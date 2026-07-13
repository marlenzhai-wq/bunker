"""Ойыншы карточкаларын генерациялау қызметі."""
import json
import os
import random
from typing import Any

from config import DATA_DIR
from database.player_repository import player_repository
from utils.logger import get_logger

logger = get_logger(__name__)

# card өрісі -> JSON файл атауы
FIELD_FILES = {
    "profession": "professions.json",
    "health": "health.json",
    "hobby": "hobbies.json",
    "phobia": "phobias.json",
    "special_skill": "skills.json",
    "item": "items.json",
    "trait": "traits.json",
    "biological_feature": "biology.json",
}

GENDERS = ["Ер", "Әйел"]

_cache: dict[str, list[str]] = {}


def _load(field: str) -> list[str]:
    if field not in _cache:
        path = os.path.join(DATA_DIR, FIELD_FILES[field])
        with open(path, "r", encoding="utf-8") as f:
            _cache[field] = json.load(f)
    return _cache[field]


def reload_data() -> None:
    """JSON файлдарын кэштен тазалап, келесі жолы қайта оқиды.
    Жаңа мәндер қосқаннан кейін ботты қайта іске қоспай-ақ шақыруға болады."""
    _cache.clear()


async def generate_card(game_id: int) -> dict[str, Any]:
    """Ойыншы үшін карточка генерациялайды. Мүмкіндігінше осы ойында
    бұрын қолданылған мәндерді қайталамауға тырысады."""
    card: dict[str, Any] = {
        "age": random.randint(16, 78),
        "gender": random.choice(GENDERS),
    }

    for field in FIELD_FILES:
        pool = _load(field)
        used = await player_repository.used_values(game_id, field)
        available = [v for v in pool if v not in used]
        if not available:
            # Барлық мәндер таусылса, кез келгенін қайта қолданамыз
            available = pool
            logger.info("Field '%s' пулы таусылды, мәндер қайталанады (game_id=%s)", field, game_id)
        card[field] = random.choice(available)

    return card


CARD_LABELS = {
    "age": "👤 Жасы",
    "gender": "⚧ Жынысы",
    "profession": "💼 Мамандығы",
    "health": "❤️ Денсаулығы",
    "phobia": "😨 Фобиясы",
    "hobby": "🎯 Хоббиі",
    "trait": "🧠 Мінезі",
    "biological_feature": "🧬 Биологиялық ерекшелігі",
    "special_skill": "✨ Қосымша қабілеті",
    "item": "🎁 Заты",
}

CARD_ORDER = [
    "age", "gender", "profession", "health", "phobia",
    "hobby", "trait", "biological_feature", "special_skill", "item",
]


def format_card(card: dict[str, Any], title: str = "📋 Сіздің картаңыз") -> str:
    lines = [f"<b>{title}</b>", ""]
    for field in CARD_ORDER:
        if field in card:
            lines.append(f"{CARD_LABELS[field]}: {card[field]}")
    return "\n".join(lines)
