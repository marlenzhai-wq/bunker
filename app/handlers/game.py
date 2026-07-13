"""Game control commands.  Every entry point checks current role access."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.services.access_control import AccessControl
from app.repositories.game_repository import GameSession
from app.services.game_control import GameControlService, GameStateError


router = Router(name="game_control")
audit_log = logging.getLogger("bunker.audit")


async def _require_game_manager(message: Message, access: AccessControl) -> bool:
    user = message.from_user
    if user and await access.is_game_manager(user.id):
        return True
    actor_id = user.id if user else None
    audit_log.warning("GAME_CONTROL denied actor_id=%s", actor_id)
    await message.answer("⛔ Ойынды тек бас админ немесе жүргізуші басқара алады.")
    return False


async def _run_control(
    message: Message,
    action: str,
    operation: Callable[[], Awaitable[GameSession]],
) -> bool:
    try:
        session = await operation()
    except GameStateError as error:
        await message.answer(f"ℹ️ {error}")
        return False
    audit_log.info(
        "GAME_CONTROL action=%s actor_id=%s status=%s round=%s",
        action,
        message.from_user.id,
        session.status,
        session.round_number,
    )
    return True


@router.message(Command("startgame"))
async def start_game(message: Message, access: AccessControl, game_control: GameControlService) -> None:
    if not await _require_game_manager(message, access):
        return
    completed = await _run_control(
        message,
        "startgame",
        lambda: game_control.start_game(message.from_user.id),
    )
    if completed:
        await message.answer("✅ Тіркелу ашылды.")


@router.message(Command("go"))
@router.message(F.text == "го")
async def close_registration(
    message: Message, access: AccessControl, game_control: GameControlService
) -> None:
    if not await _require_game_manager(message, access):
        return
    try:
        await game_control.close_registration()
    except GameStateError as error:
        await message.answer(f"ℹ️ {error}")
        return
    audit_log.info("GAME_CONTROL action=go actor_id=%s", message.from_user.id)
    await message.answer("✅ Тіркелу жабылды. Ойын басталды.")


@router.message(Command("vote"))
async def start_vote(message: Message, access: AccessControl, game_control: GameControlService) -> None:
    if not await _require_game_manager(message, access):
        return
    try:
        await game_control.start_vote()
    except GameStateError as error:
        await message.answer(f"ℹ️ {error}")
        return
    audit_log.info("GAME_CONTROL action=vote actor_id=%s", message.from_user.id)
    await message.answer("✅ Дауыс беру басталды.")


@router.message(Command("next"))
async def next_round(message: Message, access: AccessControl, game_control: GameControlService) -> None:
    if not await _require_game_manager(message, access):
        return
    try:
        session = await game_control.next_round()
    except GameStateError as error:
        await message.answer(f"ℹ️ {error}")
        return
    audit_log.info(
        "GAME_CONTROL action=next actor_id=%s round=%s",
        message.from_user.id,
        session.round_number,
    )
    await message.answer(f"✅ Келесі кезең басталды. Раунд: {session.round_number}.")


@router.message(Command("endgame"))
async def end_game(message: Message, access: AccessControl, game_control: GameControlService) -> None:
    if not await _require_game_manager(message, access):
        return
    try:
        await game_control.end_game(message.from_user.id)
    except GameStateError as error:
        await message.answer(f"ℹ️ {error}")
        return
    audit_log.info("GAME_CONTROL action=endgame actor_id=%s", message.from_user.id)
    await message.answer("🛑 Ойын аяқталды.")
