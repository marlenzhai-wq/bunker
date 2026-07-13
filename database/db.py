"""SQLite дерекқорына қосылу және кестелерді инициализациялау."""
import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS hosts (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    added_by    INTEGER,
    added_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS games (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id              INTEGER,
    status                  TEXT DEFAULT 'waiting',   -- waiting | started | voting | ended
    started_by              INTEGER,
    bunker_places           INTEGER,
    current_round           INTEGER DEFAULT 0,
    registration_message_id INTEGER,
    bunker_title             TEXT,
    bunker_description       TEXT,
    disaster_title            TEXT,
    disaster_description       TEXT,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP,
    ended_at                TEXT
);

CREATE TABLE IF NOT EXISTS players (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    username    TEXT,
    first_name  TEXT,
    is_alive    INTEGER DEFAULT 1,
    card_json   TEXT,
    joined_at   TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, user_id)
);

CREATE TABLE IF NOT EXISTS votes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       INTEGER NOT NULL,
    round         INTEGER NOT NULL,
    revote_stage  INTEGER DEFAULT 0,
    voter_id      INTEGER NOT NULL,
    target_id     INTEGER NOT NULL,
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, round, revote_stage, voter_id)
);

CREATE TABLE IF NOT EXISTS game_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id     INTEGER,
    actor_id    INTEGER,
    action      TEXT,
    details     TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


class Database:
    """aiosqlite қосылымын басқаратын жеңіл орауыш (wrapper)."""

    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA foreign_keys = ON;")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Дерекқор қосылымы ашылмаған. Алдымен connect() шақырыңыз.")
        return self._conn


# Бүкіл қосымшада қолданылатын жалғыз (singleton) дерекқор нысаны
db = Database()
