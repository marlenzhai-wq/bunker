"""Жүргізушілерді (Host) басқаруға арналған репозиторий."""
from dataclasses import dataclass

from database.db import db


@dataclass
class HostRecord:
    user_id: int
    username: str | None
    first_name: str | None
    added_by: int | None


class HostRepository:
    async def add_host(self, user_id: int, username: str | None,
                        first_name: str | None, added_by: int) -> None:
        await db.conn.execute(
            """
            INSERT INTO hosts (user_id, username, first_name, added_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name
            """,
            (user_id, username, first_name, added_by),
        )
        await db.conn.commit()

    async def remove_host(self, user_id: int) -> bool:
        cursor = await db.conn.execute("DELETE FROM hosts WHERE user_id = ?", (user_id,))
        await db.conn.commit()
        return cursor.rowcount > 0

    async def is_host(self, user_id: int) -> bool:
        cursor = await db.conn.execute("SELECT 1 FROM hosts WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row is not None

    async def list_hosts(self) -> list[HostRecord]:
        cursor = await db.conn.execute(
            "SELECT user_id, username, first_name, added_by FROM hosts ORDER BY added_at"
        )
        rows = await cursor.fetchall()
        return [HostRecord(r["user_id"], r["username"], r["first_name"], r["added_by"]) for r in rows]


host_repository = HostRepository()
