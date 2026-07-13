"""Inline пернетақталар."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.player_repository import PlayerRecord


def registration_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Ойынға қосылу", callback_data="join_game")]
        ]
    )


def closed_registration_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⏳ Тіркелу жабылды", callback_data="noop")]
        ]
    )


def vote_keyboard(candidates: list[PlayerRecord], voter_id: int) -> InlineKeyboardMarkup:
    rows = []
    for p in candidates:
        if p.user_id == voter_id:
            continue
        rows.append(
            [InlineKeyboardButton(text=p.display_name, callback_data=f"vote:{p.user_id}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def my_card_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Менің картам", callback_data="my_card")]
        ]
    )
