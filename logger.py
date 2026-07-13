"""Reply (тұрақты) пернетақталар."""
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

HOST_START_VOTE = "▶ Дауыс беруді бастау"
HOST_NEXT_ROUND = "⏭ Келесі кезең"
HOST_STATUS = "📊 Ойын жағдайы"
HOST_END_GAME = "🛑 Ойынды аяқтау"
HOST_ALIVE_LIST = "👥 Тірі ойыншылар"

PLAYER_MY_CARD = "📋 Менің картам"


def host_panel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=HOST_START_VOTE), KeyboardButton(text=HOST_NEXT_ROUND)],
            [KeyboardButton(text=HOST_STATUS), KeyboardButton(text=HOST_ALIVE_LIST)],
            [KeyboardButton(text=HOST_END_GAME)],
        ],
        resize_keyboard=True,
        is_persistent=True,
    )


def player_panel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=PLAYER_MY_CARD)]],
        resize_keyboard=True,
        is_persistent=True,
    )
