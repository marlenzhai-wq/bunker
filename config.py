"""Bot configuration.

Put the Telegram ID of the single super administrator in ``SUPER_ADMIN_ID``.
The bot deliberately refuses to start while it is left as ``0``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final


# Replace 0 with the Telegram ID of the only super administrator.
SUPER_ADMIN_ID: Final[int] = 8109812467

# Keep the token out of source control.  For PowerShell:
#   $env:BOT_TOKEN = "123456:ABC..."
BOT_TOKEN: Final[str] = os.getenv("BOT_TOKEN", "8993407919:AAHsZsGGjFEjKfhL2Lrndasfi2MLj9QMVKM")
DATABASE_PATH: Final[Path] = Path(os.getenv("DATABASE_PATH", "bunker.db"))
LOG_LEVEL: Final[str] = os.getenv("LOG_LEVEL", "INFO")
CHANNEL_ID: Final[int] = -1002734539362


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    database_path: Path
    super_admin_id: int
    log_level: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            bot_token=BOT_TOKEN,
            database_path=DATABASE_PATH,
            super_admin_id=SUPER_ADMIN_ID,
            log_level=LOG_LEVEL,
        )

    def validate(self) -> None:
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN environment variable is not set.")
        if self.super_admin_id <= 0:
            raise RuntimeError(
                "Set a positive SUPER_ADMIN_ID in config.py before starting the bot."
            )
