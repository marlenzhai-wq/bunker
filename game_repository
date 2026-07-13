"""Ойын (Game) күйін дерекқорда сақтауға арналған репозиторий."""
from dataclasses import dataclass

from database.db import db


@dataclass
class GameRecord:
    id: int
    channel_id: int
    status: str
    started_by: int | None
    bunker_places: int
    current_round: int
    registration_message_id: int | None
    bunker_title: str | None
    bunker_description: str | None
    disaster_title: str | None
    disaster_description: str | None

    @property
    def is_active(self) -> bool:
        return self.status in ("waiting", "started", "voting")


def _row_to_game(row) -> GameRecord:
    return GameRecord(
        id=row["id"],
        channel_id=row["channel_id"],
        status=row["status"],
        started_by=row["started_by"],
        bunker_places=row["bunker_places"],
        current_round=row["current_round"],
        registration_message_id=row["registration_message_id"],
        bunker_title=row["bunker_title"],
        bunker_description=row["bunker_description"],
        disaster_title=row["disaster_title"],
        disaster_description=row["disaster_description"],
    )


class GameRepository:
    async def create_game(self, channel_id: int, started_by: int,
                           bunker_places: int) -> GameRecord:
        cursor = await db.conn.execute(
            """
            INSERT INTO games (channel_id, started_by, bunker_places, status)
            VALUES (?, ?, ?, 'waiting')
            """,
            (channel_id, started_by, bunker_places),
        )
        await db.conn.commit()
        game_id = cursor.lastrowid
        return await self.get_game(game_id)

    async def get_game(self, game_id: int) -> GameRecord | None:
        cursor = await db.conn.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = await cursor.fetchone()
        return _row_to_game(row) if row else None

    async def get_active_game(self, channel_id: int) -> GameRecord | None:
        cursor = await db.conn.execute(
            """
            SELECT * FROM games
            WHERE channel_id = ? AND status IN ('waiting', 'started', 'voting')
            ORDER BY id DESC LIMIT 1
            """,
            (channel_id,),
        )
        row = await cursor.fetchone()
        return _row_to_game(row) if row else None

    async def set_status(self, game_id: int, status: str) -> None:
        await db.conn.execute("UPDATE games SET status = ? WHERE id = ?", (status, game_id))
        await db.conn.commit()

    async def set_registration_message(self, game_id: int, message_id: int) -> None:
        await db.conn.execute(
            "UPDATE games SET registration_message_id = ? WHERE id = ?",
            (message_id, game_id),
        )
        await db.conn.commit()

    async def set_bunker_places(self, game_id: int, places: int) -> None:
        await db.conn.execute(
            "UPDATE games SET bunker_places = ? WHERE id = ?", (places, game_id)
        )
        await db.conn.commit()

    async def set_scenario(self, game_id: int, bunker_title: str, bunker_description: str,
                            disaster_title: str, disaster_description: str) -> None:
        await db.conn.execute(
            """
            UPDATE games SET bunker_title = ?, bunker_description = ?,
                              disaster_title = ?, disaster_description = ?
            WHERE id = ?
            """,
            (bunker_title, bunker_description, disaster_title, disaster_description, game_id),
        )
        await db.conn.commit()

    async def increment_round(self, game_id: int) -> int:
        await db.conn.execute(
            "UPDATE games SET current_round = current_round + 1 WHERE id = ?", (game_id,)
        )
        await db.conn.commit()
        game = await self.get_game(game_id)
        return game.current_round

    async def end_game(self, game_id: int) -> None:
        await db.conn.execute(
            "UPDATE games SET status = 'ended', ended_at = CURRENT_TIMESTAMP WHERE id = ?",
            (game_id,),
        )
        await db.conn.commit()


game_repository = GameRepository()
