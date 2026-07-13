import asyncio
import logging
import os
import sys
from pathlib import Path

# Жобаның негізгі қалтасын sys.path-ке міндетті түрде қосу (systemd үшін өте маңызды)
BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

# Лог жүйесін ең басында іске қосу (барлық қателер журналға түсуі үшін)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Қажетті модульдерді қауіпсіз импорттау және логтау
try:
    from aiogram import Bot, Dispatcher, Router
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.types import BotCommand
    
    from config import BOT_TOKEN
    from db import db
except Exception as e:
    logger.critical(f"Модульдерді немесе конфигурацияны импорттау кезінде критикалық қате: {e}", exc_info=True)
    sys.exit(1)

# Тексерілетін JSON файлдар тізімі
REQUIRED_JSON_FILES = [
    "biology.json", "bunker.json", "disasters.json", "health.json",
    "items.json", "phobias.json", "professions.json", "skills.json", "traits.json"
]


def check_json_files() -> None:
    """Ойынға қажетті барлық JSON файлдарының бар-жоғын тексереді."""
    missing_files = []
    for file_name in REQUIRED_JSON_FILES:
        file_path = BASE_DIR / file_name
        if not file_path.exists():
            missing_files.append(file_name)

    if missing_files:
        error_msg = f"Ойынның жұмысы үшін маңызды JSON файлдар табылмады: {', '.join(missing_files)}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)


def auto_discover_routers() -> list[Router]:
    """Негізгі қалтадағы барлық .py файлдардан Router объектілерін қауіпсіз іздейді."""
    discovered_routers = []

    for file_path in BASE_DIR.glob("*.py"):
        if file_path.name in ["main.py", "config.py", "db.py", "game_states.py"]:
            continue

        module_name = file_path.stem
        try:
            module = __import__(module_name)
            if hasattr(module, "router") and isinstance(module.router, Router):
                discovered_routers.append(module.router)
                logger.info(f"Роутер сәтті жүктелді: {module_name}.router")
        except Exception as e:
            # Импорт қателерін debug деңгейінде қалдырамыз, себебі сервистік файлдарда роутер болмауы қалыпты
            logger.debug(f"Модульді тексеру кезінде өткізіп жіберілді {module_name}: {e}")

    return discovered_routers


async def set_bot_commands(bot: Bot) -> None:
    """Бот командаларын Telegram интерфейсіне орнату."""
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
    check_json_files()
    await db.connect()
    logger.info("SQLite дерекқорына қосылу сәтті аяқталды.")
    await set_bot_commands(bot)
    logger.info("Bot started")


async def on_shutdown() -> None:
    """Бот тоқтағанда орындалатын функция."""
    logger.info("Shutdown кезеңі басталды...")
    try:
        await db.close()
        logger.info("Дерекқор байланысы сәтті жабылды.")
    except Exception as e:
        logger.error(f"Дерекқорды жабу кезінде қате шықты: {e}")
    logger.info("Bot stopped")


async def main() -> None:
    bot = None
    try:
        logger.info("Ботты инициализациялау басталды...")
        
        if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
            raise ValueError("BOT_TOKEN мәні бос немесе config.py ішінен дұрыс оқылмады!")

        # Бот пен Диспетчерді құру
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = Dispatcher()

        # Роутерлерді автоматты тіркеу
        routers = auto_discover_routers()
        if routers:
            dp.include_routers(*routers)
            logger.info(f"Жалпы тіркелген роутерлер саны: {len(routers)}")
        else:
            logger.warning("Ешқандай белсенді роутер табылмады. Хабарламалар өңделмеуі мүмкін.")

        # Оқиғаларды тіркеу
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Кезекте тұрып қалған ескі хабарламаларды өткізіп жіберу
        await bot.delete_webhook(drop_pending_updates=True)

        # Polling бастау
        logger.info("Telegram-мен байланыс орнатылуда (start_polling)...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.critical(f"Боттың негізгі жұмыс циклінде критикалық қате орын алды: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if bot and bot.session:
            await bot.session.close()
            logger.info("Бот сессиясы толық жабылды.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот жүйелік команда арқылы тоқтатылды.")
