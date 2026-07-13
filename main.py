import asyncio
import logging
import os
import sys
from pathlib import Path

# Жобаның негізгі қалтасын sys.path-ке міндетті түрде қосу
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# Лог жүйесі
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

try:
    from aiogram import Bot, Dispatcher, Router, F
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.types import BotCommand, Message, CallbackQuery
    from aiogram.filters import Command
    
    from config import BOT_TOKEN
    from db import db
    
    # Қажетті сервистерді импорттау
    import game_service
    import reply
    import inlive
except Exception as e:
    logger.critical(f"Модульдерді импорттау кезінде қате: {e}", exc_info=True)
    sys.exit(1)

REQUIRED_JSON_FILES = [
    "biology.json", "bunker.json", "disasters.json", "health.json",
    "items.json", "phobias.json", "professions.json", "skills.json", "traits.json"
]


def check_json_files() -> None:
    missing_files = [f for f in REQUIRED_JSON_FILES if not (BASE_DIR / f).exists()]
    if missing_files:
        raise FileNotFoundError(f"JSON файлдар табылмады: {', '.join(missing_files)}")


# Негізгі роутерді құру
main_router = Router(name="main_bunker_router")


# --- ХЕНДЛЕРЛЕР (КОМАНДАЛАРДЫ ӨҢДЕУ) ---

@main_router.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"Команда /start пайдаланушыдан: {message.from_user.id}")
    # reply.py-дан немесе тікелей мәтін жіберу
    await message.answer(
        "<b>Бункер ойынына қош келдіңіз!</b>\n\n"
        "Жаңа ойын бастау үшін /startgame командасын басыңыз немесе жүргізушінің нұсқауын күтіңіз.",
        reply_markup=inlive.registration_keyboard() if hasattr(inlive, "registration_keyboard") else None
    )


@main_router.message(Command("startgame"))
async def cmd_startgame(message: Message):
    logger.info(f"Команда /startgame іске қосылды. ID: {message.from_user.id}")
    if hasattr(game_service, "start_game"):
        # Егер game_service-те дайын функция болса, соны шақырамыз
        try:
            await game_service.start_game(message)
        except Exception as e:
            logger.error(f"Ойынды бастау кезінде қате: {e}")
            await message.answer("Ойынды бастау кезінде қате орын алды.")
    else:
        await message.answer("Ойынды бастау сервисі дайын емес немесе функция табылмады.")


@main_router.callback_query(F.data == "join_game")
async def callback_join_game(callback: CallbackQuery):
    logger.info(f"Ойынға қосылу сұранысы: {callback.from_user.id}")
    # Ойынға тіркелу логикасын іске қосу
    await callback.answer("Сіз тіркелдіңіз!")


@main_router.message(Command("vote"))
async def cmd_vote(message: Message):
    await message.answer("Дауыс беру кезеңі басталды.")


@main_router.message(Command("next"))
async def cmd_next(message: Message):
    await message.answer("Келесі кезеңге өту.")


@main_router.message(Command("endgame"))
async def cmd_endgame(message: Message):
    await message.answer("Ойын аяқталды.")


# --- СЕРВИСТІК БАСҚАРУ ---

async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Ботты іске қосу / Басты мәзір"),
        BotCommand(command="startgame", description="Жаңа ойын бастау"),
        BotCommand(command="vote", description="Дауыс беру кезеңін бастау"),
        BotCommand(command="next", description="Келесі кезеңге өту"),
        BotCommand(command="endgame", description="Ойынды мәжбүрлі түрде аяқтау"),
        BotCommand(command="hosts", description="Жүргізушілер тізімін көру"),
        BotCommand(command="addhost", description="Жүргізуші қосу (Тек админ)"),
        BotCommand(command="removehost", description="Жүргізушіні алып тастау"),
    ]
    await bot.set_my_commands(commands)


async def on_startup(bot: Bot) -> None:
    logger.info("Startup кезеңі басталды...")
    check_json_files()
    await db.connect()
    await set_bot_commands(bot)
    logger.info("Bot started")


async def on_shutdown() -> None:
    logger.info("Shutdown кезеңі басталды...")
    await db.close()
    logger.info("Bot stopped")


async def main() -> None:
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Негізгі роутерді диспетчерге міндетті түрде тіркеу
    dp.include_router(main_router)
    logger.info("Негізгі командалар роутері сәтті тіркелді.")

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Telegram-мен байланыс орнатылуда (start_polling)...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот тоқтатылды.")
