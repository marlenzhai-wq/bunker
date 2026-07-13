"""
Бункер ойыны — Telegram боты.

Іске қосу:
    1. .env немесе орта айнымалылары арқылы BOT_TOKEN, CHANNEL_ID, SUPER_ADMIN_ID
       мәндерін орнатыңыз (config.py қараңыз).
    2. pip install -r recuirments.txt
    3. python main.py

Жобаның құрылымы:
    config.py            — баптаулар
    database/            — SQLite репозиторийлері (db, game, player, host, vote, log)
    services/             — ойын логикасы (card_service, game_service, scenario_service)
    keyboards/            — reply/inline пернетақталар
    filters.py            — IsHost / IsSuperAdmin фильтрлері
    game_states.py         — FSM күйлері
    utils/logger.py        — логтау
    data/                 — карточка мәндерінің JSON файлдары
"""
import asyncio
import random

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from config import (
    BOT_TOKEN,
    CHANNEL_ID,
    DEFAULT_BUNKER_PLACES,
    MIN_PLAYERS_TO_START,
    SUPER_ADMIN_ID,
    VOTE_TIMER_SECONDS,
)
from database.db import db
from database.game_repository import GameRecord, game_repository
from database.host_repository import host_repository
from database.log_repository import log_repository
from database.player_repository import PlayerRecord, player_repository
from database.vote_repository import vote_repository
from filters import IsHost, IsSuperAdmin
from game_states import AddHostStates, StartGameStates
from keyboards.inline import my_card_inline, vote_keyboard
from keyboards.reply import (
    HOST_ALIVE_LIST,
    HOST_END_GAME,
    HOST_NEXT_ROUND,
    HOST_START_VOTE,
    HOST_STATUS,
    PLAYER_MY_CARD,
    host_panel_keyboard,
    player_panel_keyboard,
)
from services import game_service
from services.card_service import format_card, generate_card
from utils.logger import get_logger, setup_logging

logger = get_logger(__name__)

router = Router(name="main")


# ==========================================================================
# Дауыс беру сессияларын жадыда (in-memory) сақтау
# ==========================================================================
class VoteSession:
    """Бір ойынға арналған белсенді дауыс беру турының жадыдағы жазбасы."""

    def __init__(
        self,
        game_id: int,
        round_: int,
        revote_stage: int,
        candidates: list[PlayerRecord],
        message_id: int,
    ) -> None:
        self.game_id = game_id
        self.round = round_
        self.revote_stage = revote_stage
        self.candidates = candidates
        self.message_id = message_id
        self.task: asyncio.Task | None = None


vote_sessions: dict[int, VoteSession] = {}


# ==========================================================================
# /start
# ==========================================================================
@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    if user is None:
        return

    if user.id == SUPER_ADMIN_ID:
        await message.answer(
            "👑 Сәлем, Бас Админ!\n\n"
            "/addhost — жаңа жүргізуші қосу\n"
            "/removehost — жүргізушіні өшіру\n"
            "/hosts — жүргізушілер тізімі\n\n"
            "Сізде жүргізуші құқығы да автоматты түрде бар — /startgame арқылы ойын бастай аласыз.",
            reply_markup=host_panel_keyboard(),
        )
        return

    if await host_repository.is_host(user.id):
        await message.answer(
            "🎮 Сәлем, жүргізуші!\n\n"
            "/startgame — жаңа ойын баптап, тіркелуді ашу\n"
            "«го» деп жазу — тіркелуді жабып, ойынды бастау\n\n"
            "Төмендегі басқару панелін қолданыңыз:",
            reply_markup=host_panel_keyboard(),
        )
        return

    await message.answer(
        "🛡 <b>Бункер</b> ойынына қош келдіңіз!\n\n"
        "Ойынға қосылу үшін каналдағы тіркелу хабарламасындағы "
        "«➕ Ойынға қосылу» батырмасын басыңыз.\n"
        "Карточкаңызды осы жеке чаттан кез келген уақытта көре аласыз.",
        reply_markup=player_panel_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    if await state.get_state() is None:
        return
    await state.clear()
    await message.answer("Әрекет тоқтатылды.")


# ==========================================================================
# Бас админ командалары: жүргізушілерді басқару
# ==========================================================================
async def _process_addhost(message: Message, raw_id: str) -> None:
    raw_id = raw_id.strip()
    if not raw_id.lstrip("-").isdigit():
        await message.answer("⚠ ID тек сан түрінде болу керек. /addhost командасын қайта жіберіңіз.")
        return
    user_id = int(raw_id)
    await host_repository.add_host(user_id, username=None, first_name=None, added_by=message.from_user.id)
    await log_repository.log(message.from_user.id, "add_host", details=str(user_id))
    await message.answer(f"✅ {user_id} енді жүргізуші болып тағайындалды.")


@router.message(Command("addhost"), IsSuperAdmin())
async def cmd_addhost(message: Message, command: CommandObject, state: FSMContext) -> None:
    if command.args:
        await _process_addhost(message, command.args)
        return
    await state.set_state(AddHostStates.waiting_for_id)
    await message.answer("Жаңа жүргізушінің Telegram ID-сын жіберіңіз (немесе /cancel):")


@router.message(StateFilter(AddHostStates.waiting_for_id), IsSuperAdmin())
async def process_addhost_id(message: Message, state: FSMContext) -> None:
    await state.clear()
    await _process_addhost(message, message.text or "")


@router.message(Command("removehost"), IsSuperAdmin())
async def cmd_removehost(message: Message, command: CommandObject) -> None:
    args = (command.args or "").strip()
    if not args.lstrip("-").isdigit():
        await message.answer("Қолданылуы: /removehost <telegram_id>")
        return
    user_id = int(args)
    removed = await host_repository.remove_host(user_id)
    if removed:
        await log_repository.log(message.from_user.id, "remove_host", details=str(user_id))
        await message.answer(f"🗑 {user_id} жүргізушілер тізімінен өшірілді.")
    else:
        await message.answer("Мұндай жүргізуші табылмады.")


@router.message(Command("hosts"), IsSuperAdmin())
async def cmd_hosts(message: Message) -> None:
    hosts = await host_repository.list_hosts()
    if not hosts:
        await message.answer("Әзірге жүргізушілер қосылмаған.")
        return
    lines = [
        f"{i}. {h.first_name or (h.username and f'@{h.username}') or h.user_id} — ID: {h.user_id}"
        for i, h in enumerate(hosts, start=1)
    ]
    await message.answer("👑 <b>Жүргізушілер тізімі</b>\n\n" + "\n".join(lines))


# ==========================================================================
# Жүргізуші: ойынды бастау / тіркелуді жабу
# ==========================================================================
@router.message(Command("startgame"), IsHost())
async def cmd_startgame(message: Message, state: FSMContext) -> None:
    if await game_service.get_active_game():
        await message.answer("⚠ Каналда әлі аяқталмаған ойын бар. Алдымен оны аяқтаңыз.")
        return
    await state.set_state(StartGameStates.waiting_for_places)
    await message.answer(
        f"Бункерде неше орын болады? Санды жіберіңіз (әдепкі: {DEFAULT_BUNKER_PLACES}):"
    )


@router.message(StateFilter(StartGameStates.waiting_for_places), IsHost())
async def process_places(message: Message, state: FSMContext, bot: Bot) -> None:
    raw = (message.text or "").strip()
    places = int(raw) if raw.isdigit() and int(raw) > 0 else DEFAULT_BUNKER_PLACES
    await state.clear()

    try:
        game = await game_service.create_game(message.from_user.id, places)
    except game_service.GameError as e:
        await message.answer(f"⚠ {e}")
        return

    await game_service.send_registration_message(bot, game)
    await log_repository.log(message.from_user.id, "start_game", details=f"places={places}", game_id=game.id)
    await message.answer(
        f"✅ Тіркелу каналда ашылды. Бункерде {places} орын бар.\n"
        "Барлық қатысушылар қосылғаннан кейін «го» деп жазыңыз.",
        reply_markup=host_panel_keyboard(),
    )


@router.message(F.text.lower() == "го", IsHost())
async def cmd_go(message: Message, bot: Bot) -> None:
    game = await game_service.get_active_game()
    if not game:
        await message.answer("Белсенді ойын жоқ.")
        return
    players_count = await player_repository.count_players(game.id)
    if players_count < MIN_PLAYERS_TO_START:
        await message.answer(f"⚠ Ойынды бастау үшін кемінде {MIN_PLAYERS_TO_START} ойыншы керек.")
        return
    try:
        await game_service.close_registration(bot, game)
    except game_service.GameError as e:
        await message.answer(f"⚠ {e}")
        return
    await log_repository.log(message.from_user.id, "close_registration", game_id=game.id)
    await message.answer("🔒 Тіркелу жабылды, ойын басталды!")


# ==========================================================================
# Жүргізуші панелі (reply keyboard)
# ==========================================================================
@router.message(F.text == HOST_STATUS, IsHost())
async def host_status(message: Message) -> None:
    game = await game_service.get_active_game()
    if not game:
        await message.answer("Белсенді ойын жоқ.")
        return
    await message.answer(await game_service.status_text(game))


@router.message(F.text == HOST_ALIVE_LIST, IsHost())
async def host_alive_list(message: Message) -> None:
    game = await game_service.get_active_game()
    if not game:
        await message.answer("Белсенді ойын жоқ.")
        return
    await message.answer(await game_service.alive_list_text(game.id))


@router.message(F.text == HOST_NEXT_ROUND, IsHost())
async def host_next_round(message: Message, bot: Bot) -> None:
    game = await game_service.get_active_game()
    if not game:
        await message.answer("Белсенді ойын жоқ.")
        return
    if game.id in vote_sessions:
        await message.answer("⚠ Ағымдағы дауыс беру аяқталмай тұрып, келесі кезеңге өтуге болмайды.")
        return
    try:
        round_no = await game_service.next_round(game)
    except game_service.GameError as e:
        await message.answer(f"⚠ {e}")
        return
    await bot.send_message(chat_id=CHANNEL_ID, text=f"🔔 <b>{round_no}-кезең басталды!</b>")
    await message.answer(f"➡ {round_no}-кезеңге өттіңіз.")


@router.message(F.text == HOST_END_GAME, IsHost())
async def host_end_game(message: Message, bot: Bot) -> None:
    game = await game_service.get_active_game()
    if not game:
        await message.answer("Белсенді ойын жоқ.")
        return
    _cancel_vote_session(game.id)
    await game_service.force_end_game(bot, game, reason=f"Жүргізуші (ID: {message.from_user.id}) аяқтады.")
    await log_repository.log(message.from_user.id, "force_end_game", game_id=game.id)
    await message.answer("🛑 Ойын аяқталды.")


@router.message(F.text == HOST_START_VOTE, IsHost())
async def host_start_vote(message: Message, bot: Bot) -> None:
    game = await game_service.get_active_game()
    if not game:
        await message.answer("Белсенді ойын жоқ.")
        return
    if game.id in vote_sessions:
        await message.answer("⚠ Дауыс беру әлдеқашан жүріп жатыр.")
        return
    if game.status not in ("started", "voting"):
        await message.answer("⚠ Ойын әлі тіркелуден өткен жоқ.")
        return

    candidates = await player_repository.list_players(game.id, alive_only=True)
    if len(candidates) < 2:
        await message.answer("⚠ Дауыс беру үшін кемінде 2 тірі ойыншы керек.")
        return

    round_no = game.current_round if game.current_round > 0 else await game_service.next_round(game)
    await message.answer("🗳 Дауыс беру каналда басталды.")
    await _start_vote(bot, game.id, round_no, candidates, revote_stage=0)


@router.message(F.text == PLAYER_MY_CARD)
async def player_my_card(message: Message) -> None:
    game = await game_service.get_active_game()
    player = await player_repository.get_player(game.id, message.from_user.id) if game else None
    if player is None:
        await message.answer("Сіз әзірге ешбір белсенді ойынға қосылған жоқсыз.")
        return
    await message.answer(format_card(player.card))


# ==========================================================================
# Ойыншы: тіркелу / карта callback-тері
# ==========================================================================
@router.callback_query(F.data == "join_game")
async def cb_join_game(callback: CallbackQuery, bot: Bot) -> None:
    game = await game_service.get_active_game()
    if not game or game.status != "waiting":
        await callback.answer("⏳ Тіркелу жабық немесе белсенді ойын жоқ.", show_alert=True)
        return

    user = callback.from_user
    if await player_repository.is_registered(game.id, user.id):
        await callback.answer("Сіз қазірдің өзінде қосылғансыз.", show_alert=True)
        return

    card = await generate_card(game.id)
    player = await player_repository.add_player(game.id, user.id, user.username, user.first_name, card)
    await game_service.refresh_registration_message(bot, game)
    await log_repository.log(user.id, "join_game", game_id=game.id)

    try:
        await bot.send_message(chat_id=user.id, text=format_card(player.card), reply_markup=my_card_inline())
        await callback.answer("✅ Ойынға қосылдыңыз! Картаңыз жеке хабарламаға жіберілді.")
    except TelegramForbiddenError:
        await callback.answer(
            "✅ Қосылдыңыз! Картаңызды алу үшін ботпен жеке чатты бастаңыз (/start).",
            show_alert=True,
        )


@router.callback_query(F.data == "my_card")
async def cb_my_card(callback: CallbackQuery) -> None:
    user = callback.from_user
    game = await game_service.get_active_game()
    player = await player_repository.get_player(game.id, user.id) if game else None
    if player is None:
        await callback.answer("Сізде белсенді карта табылмады.", show_alert=True)
        return
    await callback.message.answer(format_card(player.card))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer("⏳ Тіркелу жабылды.")


# ==========================================================================
# Дауыс беру callback-і
# ==========================================================================
@router.callback_query(F.data.startswith("vote:"))
async def cb_vote(callback: CallbackQuery, bot: Bot) -> None:
    game = await game_service.get_active_game()
    if game is None or game.id not in vote_sessions:
        await callback.answer("⏳ Дауыс беру белсенді емес.", show_alert=True)
        return

    session = vote_sessions[game.id]
    voter = callback.from_user

    voter_record = await player_repository.get_player(game.id, voter.id)
    if voter_record is None or not voter_record.is_alive:
        await callback.answer("Сіз бұл ойында тірі ойыншы емессіз.", show_alert=True)
        return

    try:
        target_id = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer()
        return

    if target_id == voter.id:
        await callback.answer("Өзіңізге дауыс бере алмайсыз.", show_alert=True)
        return
    if target_id not in {p.user_id for p in session.candidates}:
        await callback.answer("Бұл ойыншы осы дауыс беруге қатыспайды.", show_alert=True)
        return

    cast = await vote_repository.cast_vote(game.id, session.round, session.revote_stage, voter.id, target_id)
    if not cast:
        await callback.answer("Сіз бұл кезеңде бұрын дауыс бердіңіз.", show_alert=True)
        return

    await callback.answer("✅ Дауысыңыз қабылданды.")

    voters_count = await vote_repository.count_voters(game.id, session.round, session.revote_stage)
    if voters_count >= len(session.candidates):
        await _finish_vote(bot, game.id)


# ==========================================================================
# Дауыс беруді ұйымдастыратын көмекші функциялар
# ==========================================================================
def _cancel_vote_session(game_id: int) -> None:
    session = vote_sessions.pop(game_id, None)
    if session and session.task and not session.task.done():
        session.task.cancel()


async def _start_vote(
    bot: Bot,
    game_id: int,
    round_no: int,
    candidates: list[PlayerRecord],
    revote_stage: int,
) -> None:
    await game_repository.set_status(game_id, "voting")

    stage_label = f" (қайта дауыс беру №{revote_stage})" if revote_stage else ""
    text = (
        f"🗳 <b>{round_no}-кезең дауыс беруі{stage_label}</b>\n\n"
        "Бункерден кетуі керек ойыншыны таңдаңыз:\n\n"
        + "\n".join(f"• {p.display_name}" for p in candidates)
        + f"\n\n⏳ Уақыт: {VOTE_TIMER_SECONDS} секунд."
    )
    msg = await bot.send_message(
        chat_id=CHANNEL_ID, text=text, reply_markup=vote_keyboard(candidates, voter_id=0)
    )

    session = VoteSession(game_id, round_no, revote_stage, candidates, msg.message_id)
    vote_sessions[game_id] = session
    session.task = asyncio.create_task(_vote_timeout(bot, game_id))


async def _vote_timeout(bot: Bot, game_id: int) -> None:
    try:
        await asyncio.sleep(VOTE_TIMER_SECONDS)
    except asyncio.CancelledError:
        return
    if game_id in vote_sessions:
        await _finish_vote(bot, game_id)


async def _finish_vote(bot: Bot, game_id: int) -> None:
    session = vote_sessions.pop(game_id, None)
    if session is None:
        return
    if session.task and not session.task.done():
        session.task.cancel()

    try:
        await bot.edit_message_reply_markup(chat_id=CHANNEL_ID, message_id=session.message_id, reply_markup=None)
    except TelegramAPIError as e:
        logger.warning("Дауыс беру хабарламасының пернетақтасын жою сәтсіз: %s", e)

    game = await game_repository.get_game(game_id)
    if game is None:
        return

    tally = await vote_repository.tally(game_id, session.round, session.revote_stage)

    if not tally:
        await bot.send_message(chat_id=CHANNEL_ID, text="🤷 Ешкім дауыс бермеді. Бұл кезеңде ешкім шығарылмайды.")
        await game_repository.set_status(game_id, "started")
        return

    lines = [f"{p.display_name}: {tally.get(p.user_id, 0)} дауыс" for p in session.candidates]
    await bot.send_message(chat_id=CHANNEL_ID, text="📊 <b>Дауыс беру нәтижесі</b>\n\n" + "\n".join(lines))

    max_votes = max(tally.values())
    top = [uid for uid, count in tally.items() if count == max_votes]

    if len(top) == 1:
        ended = await game_service.eliminate_and_report(bot, game, top[0])
        if not ended:
            await game_repository.set_status(game_id, "started")
        return

    if session.revote_stage >= 2:
        chosen = random.choice(top)
        await bot.send_message(
            chat_id=CHANNEL_ID,
            text="⚖ Дауыстар бірнеше рет тең түскендіктен, шешім кездейсоқ таңдаумен қабылданды.",
        )
        ended = await game_service.eliminate_and_report(bot, game, chosen)
        if not ended:
            await game_repository.set_status(game_id, "started")
        return

    tied_candidates = [p for p in session.candidates if p.user_id in top]
    await bot.send_message(chat_id=CHANNEL_ID, text="⚖ Дауыстар тең түсті! Қайта дауыс беру басталады.")
    await _start_vote(bot, game_id, session.round, tied_candidates, revote_stage=session.revote_stage + 1)


# ==========================================================================
# Бот құрылымы мен іске қосу нүктесі
# ==========================================================================
async def on_startup(bot: Bot) -> None:
    await db.connect()
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Бот сәтті іске қосылды.")


async def on_shutdown(bot: Bot) -> None:
    await db.close()
    logger.info("Бот тоқтатылды, дерекқор жабылды.")


async def main() -> None:
    setup_logging()

    if not BOT_TOKEN or BOT_TOKEN == "PASTE_YOUR_BOT_TOKEN_HERE":
        raise RuntimeError("BOT_TOKEN орнатылмаған. config.py немесе орта айнымалысын тексеріңіз.")
    if not CHANNEL_ID:
        raise RuntimeError("CHANNEL_ID орнатылмаған. config.py немесе орта айнымалысын тексеріңіз.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот қолмен тоқтатылды.")
