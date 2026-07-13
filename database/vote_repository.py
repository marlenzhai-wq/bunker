"""Дауыс беруге арналған репозиторий."""
from collections import Counter

from database.db import db


class VoteRepository:
    async def cast_vote(self, game_id: int, round_: int, revote_stage: int,
                         voter_id: int, target_id: int) -> bool:
        """Дауысты жазады. Егер ойыншы бұл кезеңде бұрын дауыс берген болса False қайтарады."""
        try:
            await db.conn.execute(
                """
                INSERT INTO votes (game_id, round, revote_stage, voter_id, target_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (game_id, round_, revote_stage, voter_id, target_id),
            )
            await db.conn.commit()
            return True
        except Exception:
            return False

    async def has_voted(self, game_id: int, round_: int, revote_stage: int, voter_id: int) -> bool:
        cursor = await db.conn.execute(
            """
            SELECT 1 FROM votes
            WHERE game_id = ? AND round = ? AND revote_stage = ? AND voter_id = ?
            """,
            (game_id, round_, revote_stage, voter_id),
        )
        return (await cursor.fetchone()) is not None

    async def count_voters(self, game_id: int, round_: int, revote_stage: int) -> int:
        cursor = await db.conn.execute(
            """
            SELECT COUNT(*) as c FROM votes
            WHERE game_id = ? AND round = ? AND revote_stage = ?
            """,
            (game_id, round_, revote_stage),
        )
        row = await cursor.fetchone()
        return row["c"]

    async def tally(self, game_id: int, round_: int, revote_stage: int) -> Counter:
        cursor = await db.conn.execute(
            """
            SELECT target_id FROM votes
            WHERE game_id = ? AND round = ? AND revote_stage = ?
            """,
            (game_id, round_, revote_stage),
        )
        rows = await cursor.fetchall()
        return Counter(r["target_id"] for r in rows)


vote_repository = VoteRepository()
