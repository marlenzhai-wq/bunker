import asyncio
import logging
import os
import sys
import types
from pathlib import Path

# Жобаның негізгі қалтасын sys.path-ке қосу
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# ЛОГ ЖҮЙЕСІ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# --- СИСТЕМАНЫ АЛДАУ (ВИРТУАЛДЫ МОДУЛЬДЕР) ---
try:
    # 1. 'database' модуліне сілтеме
    if 'database' not in sys.modules:
        db_module = types.ModuleType('database')
        db_module.__path__ = [str(BASE_DIR)]
        sys.modules['database'] = db_module
        logger.info("Жоба құрылымы үшін 'database' виртуалды сілтемесі жасалды.")

    # 2. 'keyboards' және 'keyboards.inline' модульдеріне сілтеме
    import inlive
    if 'keyboards' not in sys.modules:
        keyboards_module = types.ModuleType('keyboards')
        inline_module = types.ModuleType('keyboards.inline')
        for attr in dir(inlive):
            if not attr.startswith('__'):
                setattr(inline_module, attr, getattr(inlive, attr))
        keyboards_module.inline = inline_module
        sys.modules['keyboards'] = keyboards_module
        sys.modules['keyboards.inline'] = inline_module
        logger.info("Жоба құрылымы үшін 'keyboards.inline' виртуалды сілтемесі жасалды.")

    # 3. 'services' модуліне сілтеме
    if 'services' not in sys.modules:
        services_module = types.ModuleType('services')
        services_module.__path__ = [str(BASE_DIR)]
        sys.modules['services'] = services_module
        logger.info("Жоба құрылымы үшін 'services' виртуалды сілтемесі жасалды.")

    # 4. 'utils' және 'utils.logger' модульдеріне сілтеме (Жаңадан қосылды)
    if 'utils' not in sys.modules:
        utils_module = types.ModuleType('utils')
        logger_module = types.ModuleType('utils.logger')
        
        # get_logger функциясы шақырылса, стандартты логгерді қайтаратындай етеміз
        def get_logger(name=None):
            return logging.getLogger(name or "bunker_bot")
            
        setattr(logger_module, 'get_logger', get_logger)
        utils_module.logger = logger_module
        
        sys.modules['utils'] = utils_module
        sys.modules['utils.logger'] = logger_module
        logger.info("Жоба құрылымы үшін 'utils.logger' виртуалды сілтемесі жасалды.")

except Exception as e:
    logger.error(f"Виртуалды модульдерді жасау кезінде қате: {e}", exc_info=True)

# --- МОДУЛЬДЕРДІ ИМПОРТТАУ ---
try:
    from aiogram import Bot, Dispatcher, Router, F
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.types import BotCommand, Message, CallbackQuery
    from aiogram.filters import Command
    
    from config import BOT_TOKEN
    from db import db
    
    # Модульдер енді толықтай жүктеледі
    import game_service
    import reply
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

# Командаларды тікелей өңдеуге арналған роутер
main_router = Router(name="main_bunker_router")

# --- ХЕНДЛЕРЛЕР ---

@main_router.message(Command("start"))
async def cmd_start(message: Message):
    logger.info(f"Команда /start пайдаланушыдан: {message.from_user.id}")
    await message.answer(
        "<b>Бункер ойынына қош келдіңіз!</b>\n\n"
        "Жаңа ойын бастау үшін /startgame командасын басыңыз немесе жүргізушінің нұсқауын күтіңіз.",
        reply_markup=inlive.registration_keyboard() if hasattr(inlive, "registration_keyboard") else None
    )

@main_router.message(Command("startgame"))
async def cmd_startgame(message: Message):
    logger.info(f"Команда /startgame іске қосылды. ID: {message.from_user.id}")
    if hasattr(game_service, "start_game"):
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
    await callback.answer("Сіз тіркелдіңіз!")

# --- СЕРВИСТІК БАСҚАРУ ---

async def set_bot_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Ботты іске қосу / Басты мәзір"),
        BotCommand(command="startgame", description="Жаңа ойын бастау"),
        BotCommand(command="vote", description="Дауыс беру кезеңін бастау"),
        BotCommand(command="next", description="Келесі кезеңге өту"),
        BotCommand(command="endgame", description="Ойынды мәжбүрлі түрде аяқтау"),
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
    dp.include_router(main_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Telegram-мен байланыс орнатылуда (start_polling)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот тоқтатылды.")
