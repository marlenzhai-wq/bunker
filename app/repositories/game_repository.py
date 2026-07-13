"""Durable minimal game-session state for protected control commands.

The gameplay module can grow independently while these state transitions keep
the host permissions demonstrably wired into real, restart-safe commands.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.database import Database


_UNSET = object()


@dataclass(frozen=True, slots=True)
class GameSession:
    status: str
    round_number: int
    started_by: int | None
    ended_by: int | None


class GameRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create_schema(self) -> None:
        async with self._database.lock:
            await self._database.connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS game_session (
                    singleton    INTEGER PRIMARY KEY CHECK (singleton = 1),
                    status       TEXT NOT NULL,
                    round_number INTEGER NOT NULL DEFAULT 0,
                    started_by   INTEGER,
                    ended_by     INTEGER,
                    updated_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT OR IGNORE INTO game_session (singleton, status)
                VALUES (1, 'idle');
                """
            )
            await self._database.connection.commit()

    async def get(self) -> GameSession:
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                "SELECT status, round_number, started_by, ended_by FROM game_session WHERE singleton = 1"
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:  # Defensive: create_schema is called at application start.
            raise RuntimeError("Game-session row is missing.")
        return GameSession(**dict(row))

    async def update(
        self,
        *,
        status: str,
        round_number: int | object = _UNSET,
        started_by: int | None | object = _UNSET,
        ended_by: int | None | object = _UNSET,
    ) -> GameSession:
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                "SELECT status, round_number, started_by, ended_by FROM game_session WHERE singleton = 1"
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise RuntimeError("Game-session row is missing.")
            current = GameSession(**dict(row))
            next_round = current.round_number if round_number is _UNSET else round_number
            next_started_by = current.started_by if started_by is _UNSET else started_by
            next_ended_by = current.ended_by if ended_by is _UNSET else ended_by
            await self._database.connection.execute(
                """
                UPDATE game_session
                SET status = ?, round_number = ?, started_by = ?, ended_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE singleton = 1
                """,
                (status, next_round, next_started_by, next_ended_by),
            )
            await self._database.connection.commit()
        return GameSession(
            status,
            int(next_round),
            next_started_by if isinstance(next_started_by, int) else None,
            next_ended_by if isinstance(next_ended_by, int) else None,
        )

    async def transition(
        self,
        *,
        allowed_statuses: frozenset[str],
        status: str,
        started_by: int | None | object = _UNSET,
        ended_by: int | None | object = _UNSET,
        advance_round: bool = False,
        reset_round: bool = False,
    ) -> GameSession | None:
        """Atomically change state only when the current state is allowed."""
        async with self._database.lock:
            cursor = await self._database.connection.execute(
                "SELECT status, round_number, started_by, ended_by FROM game_session WHERE singleton = 1"
            )
            row = await cursor.fetchone()
            await cursor.close()
            if row is None:
                raise RuntimeError("Game-session row is missing.")
            current = GameSession(**dict(row))
            if current.status not in allowed_statuses:
                return None

            next_round = 0 if reset_round else current.round_number + int(advance_round)
            next_started_by = current.started_by if started_by is _UNSET else started_by
            next_ended_by = current.ended_by if ended_by is _UNSET else ended_by
            await self._database.connection.execute(
                """
                UPDATE game_session
                SET status = ?, round_number = ?, started_by = ?, ended_by = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE singleton = 1
                """,
                (status, next_round, next_started_by, next_ended_by),
            )
            await self._database.connection.commit()
        return GameSession(
            status,
            next_round,
            next_started_by if isinstance(next_started_by, int) else None,
            next_ended_by if isinstance(next_ended_by, int) else None,
        )
