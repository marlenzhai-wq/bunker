"""Persistent repository for the host role."""

from __future__ import annotations

from dataclasses import dataclass

from app.database import Database


@dataclass(frozen=True, slots=True)
class Host:
    user_id: int
    username: str | None
    display_name: str
    added_by: int
    added_at: str

    @property
    def label(self) -> str:
        return f"@{self.username}" if self.username else self.display_name


class HostRepository:
    """Stores hosts in SQLite, never in process memory."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_schema(self) -> None:
        async with self._database.lock:
            await self._database.connection.execute(
                """
                CREATE TABLE IF NOT EXISTS hosts (
                    user_id      INTEGER PRIMARY KEY,
                    username     TEXT,
                    display_name TEXT NOT NULL,
                    added_by     INTEGER NOT NULL,
                    added_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            await self._database.connection.commit()

    async def add(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str,
        added_by: int,
    ) -> bool:
        """Add or refresh a host.  Returns True only for a new host."""
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                "SELECT 1 FROM hosts WHERE user_id = ?", (user_id,)
            )
            already_exists = await cursor.fetchone() is not None
            await cursor.close()
            await self._database.connection.execute(
                """
                INSERT INTO hosts (user_id, username, display_name, added_by)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    display_name = excluded.display_name,
                    added_by = excluded.added_by
                """,
                (user_id, username, display_name, added_by),
            )
            await self._database.connection.commit()
        return not already_exists

    async def remove(self, user_id: int) -> bool:
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                "DELETE FROM hosts WHERE user_id = ?", (user_id,)
            )
            await self._database.connection.commit()
            removed = cursor.rowcount > 0
            await cursor.close()
        return removed

    async def is_host(self, user_id: int) -> bool:
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                "SELECT 1 FROM hosts WHERE user_id = ?", (user_id,)
            )
            found = await cursor.fetchone() is not None
            await cursor.close()
        return found

    async def list_all(self) -> list[Host]:
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                """
                SELECT user_id, username, display_name, added_by, added_at
                FROM hosts
                ORDER BY lower(display_name), user_id
                """
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [Host(**dict(row)) for row in rows]
