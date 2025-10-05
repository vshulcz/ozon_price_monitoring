from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    database_path: str
    log_level: str = "INFO"

    @staticmethod
    def from_env() -> "Settings":
        token = os.getenv("BOT_TOKEN")
        if not token:
            raise RuntimeError("BOT_TOKEN is not set. Provide it via env or .env file.")

        db_path = os.getenv("DATABASE_PATH", "./ozonbot.db")
        return Settings(
            bot_token=token,
            database_path=db_path,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
