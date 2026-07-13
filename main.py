import asyncio
import logging
import os
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

# Проект модульдерін импорттау
try:
    from config import BOT_TOKEN
    from db import db
except ImportError as e:
    logging.error(f"Қажетті модульдерді импорттау мүмкін болмады: {e}")
    sys.exit(1)

# Лог жүйесін баптау (systemd журналымен жақсы жұмыс істеуі үшін stdout-қа бағыттау)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Тексерілуі тиіс қажетті JSON файлдардың тізімі
REQUIRED_JSON_FILES = [
    "biology.json",
    "bunker.json",
    "disasters.json",
    "health.json",
    "items.json",
    "phobias.json",
    "professions.json",
    "skills.json",
    "traits.json",
]


def check_json_files() -> None:
    """Ойынға қажетті барлық JSON файлдарының бар-жоғын тексереді."""
    missing_files = []
    base_dir = Path(__file__).parent

    for file_name in REQUIRED_JSON_FILES:
        file_path = base_dir / file_name
        if not file_path.exists():
            missing_files.append(file_name)

    if missing_files:
        error_msg = f"Ойынның жұмысы үшін маңызды JSON файлдар табылмады: {', '.join(missing_files)}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)


def auto_discover_routers() -> list[Router]:
    """handlers немесе routers қалтасындағы барлық Router объектілерін автоматты түрде тауып қайтарады."""
    base_dir = Path(__file__).parent
    handlers_dir = base_dir / "handlers"
    routers_dir = base_dir / "routers"

    target_dir = None
    if handlers_dir.is_dir():
        target_dir = handlers_dir
    elif routers_dir.is_dir():
        target_dir = routers_dir

    if not target_dir:
        error_msg = (
            "Жоба құрылымынан 'handlers' немесе 'routers' қалтасы табылмады. "
            "Роутерлерді автоматты тіркеу мүмкін емес."
        )
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    discovered_routers = []
    dir_name = target_dir.name

    # Қалта ішіндегі барлық .py файлдарды іздеу
    for file_path in target_dir.glob("*.py"):
        if file_path.name == "__init__.py":
            continue

        module_name = f"{dir_name}.{file_path.stem}"
        try:
            # Модульді динамикалық түрде импорттау
            module = __import__(module_name, fromlist=["router"])
            if hasattr(module, "router") and isinstance(module.router, Router):
                discovered_routers.append(module.router)
                logger.info(f"Роутер сәтті табылды және жүктелді: {module_name}.router")
            else:
                logger.warning(
                    f"Модульде '{module_name}' ішінде 'router' объектісі табылмады немесе ол Router типіне жатпайды."
                )
        except Exception as e:
            logger.error(f"Модульді жүктеу кезінде қате кетті {module_name}: {e}")

    return discovered_routers


async def set_bot_commands(bot: Bot) -> None:
    """Бот командаларын Telegram интерфейсінде орнату."""
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
    logger.info("Бот командалары сәтті орнатылды.")


async def on_startup(bot: Bot) -> None:
    """Бот іске қосылғанда орындалатын функция."""
    logger.info("Startup кезеңі басталды...")

    # 1. JSON файлдарын тексеру
    check_json_files()

    # 2. Дерекқорға қосылу
    await db.connect()
    logger.info("SQLite дерекқорына қосылу сәтті аяқталды (database.db).")

    # 3. Командаларды орнату
    await set_bot_commands(bot)

    logger.info("Bot started")


async def on_shutdown() -> None:
    """Бот тоқтағанда орындалатын функция."""
    logger.info("Shutdown кезеңі басталды...")

    # 1. Дерекқор байланысын жабу
    try:
        await db.close()
        logger.info("Дерекқор байланысы сәтті жабылды.")
    except Exception as e:
        logger.error(f"Дерекқорды жабу кезінде қате шықты: {e}")

    logger.info("Bot stopped")


async def main() -> None:
    # Бот объектісін жасау (Әдепкі ParseMode HTML ретінде орнатылған)
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Диспетчерді жасау
    dp = Dispatcher()

    # Роутерлерді автоматты түрде тауып тіркеу
    routers = auto_discover_routers()
    if routers:
        dp.include_routers(*routers)
        logger.info(f"Жалпы тіркелген роутерлер саны: {len(routers)}")
    else:
        logger.warning("Ешқандай роутер тіркелген жоқ!")

    # Startup және Shutdown оқиғаларын тіркеу
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Саябыр түрде (глушение) басқа сессияларды өткізіп жіберу
    await bot.delete_webhook(drop_pending_updates=True)

    # Polling режимінде ботты іске қосу
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.critical(f"Боттың жұмысы кезінде күтпеген қате орын алды: {e}", exc_info=True)
    finally:
        await bot.session.close()
        logger.info("Бот сессиясы жабылды.")


if __name__ == "__main__":
    if sys.platform == "win32":
        # Windows жүйесінде кездесетін SelectorEventLoop қателерінің алдын алу
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот қолмен (Ctrl+C) немесе жүйелік сигнал арқылы тоқтатылды.")
