import asyncio
import logging
import os
import sys
import types
from pathlib import Path

# Жобаның негізгі қалтасы
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# ЛОГ ЖҮЙЕСІ
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# --- СЕНІМДІ ИМПОРТ ИМПОРТЕРІ (DYNAMIC PATH ALIAS) ---
class CustomPathImporter:
    """Кез келген 'services.xxx', 'database.xxx', 'utils.xxx' сұраныстарын
    тікелей негізгі қалтадағы файлдарға бағыттайтын динамикалық импортер."""
    def find_spec(self, fullname, path, target=None):
        parts = fullname.split('.')
        # Егер сұраныс біздің виртуалды бумаларға қатысты болса
        if parts[0] in ['services', 'database', 'utils', 'keyboards']:
            # Ішкі файлдың атын анықтаймыз (мысалы: scenario_service)
            mod_name = parts[-1] if len(parts) > 1 else None
            
            # Егер бұл keyboards.inline болса, оны inlive файлына сілтейміз
            if fullname == 'keyboards.inline':
                mod_name = 'inlive'
                
            if mod_name:
                # Дискіде осындай .py файлы бар ма тексереміз
                file_path = BASE_DIR / f"{mod_name}.py"
                if file_path.exists():
                    import importlib.util
                    return importlib.util.spec_from_file_location(fullname, str(file_path))
            
            # Егер бұл негізгі буманың өзі болса (мысалы, жай ғана 'services')
            spec = importlib.util.spec_from_loader(fullname, loader=None)
            spec.submodule_search_locations = [str(BASE_DIR)]
            return spec
        return None

# Импортерді жүйенің ең алдына тіркейміз
sys.meta_path.insert(0, CustomPathImporter())

# logger үшін арнайы көпір (кард-сервис іздейтін болғандықтан)
if 'utils' not in sys.modules:
    utils_mod = types.ModuleType('utils')
    log_mod = types.ModuleType('utils.logger')
    log_mod.get_logger = lambda name=None: logging.getLogger(name or "bunker_bot")
    utils_mod.logger = log_mod
    sys.modules['utils'] = utils_mod
    sys.modules['utils.logger'] = log_mod

logger.info("Барлық ішкі импорттар үшін динамикалық жүйе іске қосылды.")

# --- МОДУЛЬДЕРДІ ИМПОРТТАУ ---
try:
    from aiogram import Bot, Dispatcher, Router, F
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.types import BotCommand, Message, CallbackQuery
    from aiogram.filters import Command
    
    from config import BOT_TOKEN
    from db import db
    
    # Енді бұл модульдер кез келген ішкі импортты (scenario_service т.б.) қатесіз табады
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
