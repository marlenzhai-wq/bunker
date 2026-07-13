"""Ойыншыларды және олардың карточкаларын басқаруға арналған репозиторий."""
import json
from dataclasses import dataclass
from typing import Any

from database.db import db


@dataclass
class PlayerRecord:
    id: int
    game_id: int
    user_id: int
    username: str | None
    first_name: str | None
    is_alive: bool
    card: dict[str, Any]

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        if self.first_name:
            return self.first_name
        return "Ойыншы"


def _row_to_player(row) -> PlayerRecord:
    return PlayerRecord(
        id=row["id"],
        game_id=row["game_id"],
        user_id=row["user_id"],
        username=row["username"],
        first_name=row["first_name"],
        is_alive=bool(row["is_alive"]),
        card=json.loads(row["card_json"]) if row["card_json"] else {},
    )


class PlayerRepository:
    async def add_player(self, game_id: int, user_id: int, username: str | None,
                          first_name: str | None, card: dict[str, Any]) -> PlayerRecord:
        await db.conn.execute(
            """
            INSERT INTO players (game_id, user_id, username, first_name, card_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (game_id, user_id, username, first_name, json.dumps(card, ensure_ascii=False)),
        )
        await db.conn.commit()
        return await self.get_player(game_id, user_id)

    async def get_player(self, game_id: int, user_id: int) -> PlayerRecord | None:
        cursor = await db.conn.execute(
            "SELECT * FROM players WHERE game_id = ? AND user_id = ?", (game_id, user_id)
        )
        row = await cursor.fetchone()
        return _row_to_player(row) if row else None

    async def is_registered(self, game_id: int, user_id: int) -> bool:
        return (await self.get_player(game_id, user_id)) is not None

    async def list_players(self, game_id: int, alive_only: bool = False) -> list[PlayerRecord]:
        query = "SELECT * FROM players WHERE game_id = ?"
        if alive_only:
            query += " AND is_alive = 1"
        query += " ORDER BY id"
        cursor = await db.conn.execute(query, (game_id,))
        rows = await cursor.fetchall()
        return [_row_to_player(r) for r in rows]

    async def count_players(self, game_id: int, alive_only: bool = False) -> int:
        return len(await self.list_players(game_id, alive_only=alive_only))

    async def eliminate_player(self, game_id: int, user_id: int) -> None:
        await db.conn.execute(
            "UPDATE players SET is_alive = 0 WHERE game_id = ? AND user_id = ?",
            (game_id, user_id),
        )
        await db.conn.commit()

    async def used_values(self, game_id: int, field: str) -> set[str]:
        """Осы ойында берілген карточкалардағы field мәнінің жиынын қайтарады
        (карточкалардың мүмкіндігінше қайталанбауын қамтамасыз ету үшін)."""
        players = await self.list_players(game_id)
        return {p.card.get(field) for p in players if p.card.get(field)}


player_repository = PlayerRepository()
