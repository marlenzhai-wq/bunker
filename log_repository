"""Әкімшілік және ойын әрекеттерінің журналы."""
from database.db import db


class LogRepository:
    async def log(self, actor_id: int, action: str, details: str = "",
                   game_id: int | None = None) -> None:
        await db.conn.execute(
            "INSERT INTO game_log (game_id, actor_id, action, details) VALUES (?, ?, ?, ?)",
            (game_id, actor_id, action, details),
        )
        await db.conn.commit()


log_repository = LogRepository()
