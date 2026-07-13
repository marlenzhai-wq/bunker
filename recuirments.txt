"""Ойынның негізгі логикасын үйлестіретін қызмет (service)."""
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from config import CHANNEL_ID
from database.game_repository import GameRecord, game_repository
from database.player_repository import player_repository
from keyboards.inline import closed_registration_keyboard, registration_keyboard
from services.card_service import format_card
from services.scenario_service import format_scenario_message, pick_scenario
from utils.logger import get_logger

logger = get_logger(__name__)


class GameError(Exception):
    """Ойын логикасындағы күтілетін қателер үшін."""


async def get_active_game() -> GameRecord | None:
    return await game_repository.get_active_game(CHANNEL_ID)


async def create_game(started_by: int, bunker_places: int) -> GameRecord:
    existing = await get_active_game()
    if existing:
        raise GameError("Каналда әлі аяқталмаған ойын бар. Алдымен оны аяқтаңыз.")
    return await game_repository.create_game(CHANNEL_ID, started_by, bunker_places)


async def build_participants_text(game_id: int) -> str:
    players = await player_repository.list_players(game_id)
    header = f"👥 Қатысушылар ({len(players)})\n\n"
    if not players:
        return header + "Әзірге ешкім қосылған жоқ."
    lines = [f"{i}. {p.display_name}" for i, p in enumerate(players, start=1)]
    return header + "\n".join(lines)


async def send_registration_message(bot: Bot, game: GameRecord) -> int:
    text = (
        "🛡 <b>БУНКЕР ОЙЫНЫ БАСТАЛДЫ!</b>\n\n"
        "Ойынға қатысу үшін төмендегі батырманы басыңыз.\n\n"
        "⏳ Тіркелу ашық.\n\n"
        + await build_participants_text(game.id)
    )
    msg = await bot.send_message(
        chat_id=game.channel_id, text=text, reply_markup=registration_keyboard()
    )
    await game_repository.set_registration_message(game.id, msg.message_id)
    return msg.message_id


async def refresh_registration_message(bot: Bot, game: GameRecord) -> None:
    if not game.registration_message_id:
        return
    text = (
        "🛡 <b>БУНКЕР ОЙЫНЫ БАСТАЛДЫ!</b>\n\n"
        "Ойынға қатысу үшін төмендегі батырманы басыңыз.\n\n"
        "⏳ Тіркелу ашық.\n\n"
        + await build_participants_text(game.id)
    )
    try:
        await bot.edit_message_text(
            chat_id=game.channel_id,
            message_id=game.registration_message_id,
            text=text,
            reply_markup=registration_keyboard(),
        )
    except TelegramAPIError as e:
        logger.warning("Тіркелу хабарламасын жаңарту сәтсіз: %s", e)


async def close_registration(bot: Bot, game: GameRecord) -> None:
    """'го' командасы: тіркелуді жабады, сценарийді таңдап каналға жібереді."""
    if game.status != "waiting":
        raise GameError("Тіркелу тек 'waiting' күйінде жабылады.")

    players_count = await player_repository.count_players(game.id)
    if players_count < 1:
        raise GameError("Ойынға әлі ешкім қосылған жоқ.")

    await game_repository.set_status(game.id, "started")

    if game.registration_message_id:
        closed_text = (
            "🛡 <b>БУНКЕР ОЙЫНЫ БАСТАЛДЫ!</b>\n\n"
            "🔒 Тіркелу жабылды. Ойын басталды!\n\n"
            + await build_participants_text(game.id)
        )
        try:
            await bot.edit_message_text(
                chat_id=game.channel_id,
                message_id=game.registration_message_id,
                text=closed_text,
                reply_markup=closed_registration_keyboard(),
            )
        except TelegramAPIError as e:
            logger.warning("Тіркелу хабарламасын жабу сәтсіз: %s", e)

    bunker, disaster = pick_scenario()
    await game_repository.set_scenario(
        game.id, bunker["title"], bunker["description"], disaster["title"], disaster["description"]
    )
    await bot.send_message(
        chat_id=game.channel_id, text=format_scenario_message(bunker, disaster)
    )


async def next_round(game: GameRecord) -> int:
    if game.status not in ("started", "voting"):
        raise GameError("Раундты тек ойын басталғаннан кейін жылжытуға болады.")
    return await game_repository.increment_round(game.id)


async def alive_list_text(game_id: int) -> str:
    players = await player_repository.list_players(game_id, alive_only=True)
    if not players:
        return "👥 Тірі қалғандар жоқ."
    lines = [f"{i}. {p.display_name}" for i, p in enumerate(players, start=1)]
    return "👥 <b>Тірі қалғандар</b>\n\n" + "\n".join(lines)


async def status_text(game: GameRecord) -> str:
    total = await player_repository.count_players(game.id)
    alive = await player_repository.count_players(game.id, alive_only=True)
    status_map = {
        "waiting": "Тіркелу ашық",
        "started": "Ойын жүріп жатыр",
        "voting": "Дауыс беру жүріп жатыр",
        "ended": "Ойын аяқталды",
    }
    return (
        "📊 <b>Ойын жағдайы</b>\n\n"
        f"Күйі: {status_map.get(game.status, game.status)}\n"
        f"Раунд: {game.current_round}\n"
        f"Барлық қатысушылар: {total}\n"
        f"Тірі қалғандар: {alive}\n"
        f"Бункердегі орын саны: {game.bunker_places}"
    )


async def eliminate_and_report(bot: Bot, game: GameRecord, target_user_id: int) -> bool:
    """Ойыншыны шығарады, каналға нәтижені жібереді.
    Ойын аяқталса True қайтарады."""
    target = await player_repository.get_player(game.id, target_user_id)
    if target is None:
        raise GameError("Ойыншы табылмады.")

    await player_repository.eliminate_player(game.id, target_user_id)

    card_text = format_card(target.card, title="📄 Толық картасы")
    elimination_text = (
        f"❌ <b>Ойыннан шықты</b>\n\n{target.display_name}\n\n{card_text}"
    )
    await bot.send_message(chat_id=game.channel_id, text=elimination_text)

    alive_text = await alive_list_text(game.id)
    await bot.send_message(chat_id=game.channel_id, text=alive_text)

    alive_count = await player_repository.count_players(game.id, alive_only=True)
    if alive_count <= game.bunker_places:
        await finish_game(bot, game)
        return True
    return False


async def finish_game(bot: Bot, game: GameRecord) -> None:
    winners = await player_repository.list_players(game.id, alive_only=True)
    lines = [f"{i}. {p.display_name}" for i, p in enumerate(winners, start=1)]
    text = "🏆 <b>Жеңімпаздар</b>\n\n" + ("\n".join(lines) if lines else "Жеңімпаз анықталмады.")
    await bot.send_message(chat_id=game.channel_id, text=text)
    await game_repository.end_game(game.id)


async def force_end_game(bot: Bot, game: GameRecord, reason: str = "") -> None:
    await bot.send_message(
        chat_id=game.channel_id,
        text=f"🛑 <b>Ойын мәжбүрлі түрде аяқталды.</b>\n{reason}".strip(),
    )
    await game_repository.end_game(game.id)
