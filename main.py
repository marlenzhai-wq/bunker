"""Application entry point for the Bunker Telegram bot."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from app.database import Database
from app.handlers import admin_router, game_router
from app.repositories.game_repository import GameRepository
from app.repositories.host_repository import HostRepository
from app.services.access_control import AccessControl
from app.services.game_control import GameControlService
from config import Settings


async def run() -> None:
    settings = Settings.load()
    settings.validate()

    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    database = Database(settings.database_path)
    await database.connect()
    hosts = HostRepository(database)
    games = GameRepository(database)
    await hosts.create_schema()
    await games.create_schema()

    dispatcher = Dispatcher()
    dispatcher["access"] = AccessControl(
        super_admin_id=settings.super_admin_id,
        hosts=hosts,
    )
    dispatcher["hosts"] = hosts
    dispatcher["game_control"] = GameControlService(games)
    dispatcher.include_routers(admin_router, game_router)

    bot = Bot(token=settings.bot_token)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
