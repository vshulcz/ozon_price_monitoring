from __future__ import annotations

from dataclasses import dataclass

import aiosqlite

from app.i18n import Lang


@dataclass
class User:
    id: int
    tg_user_id: int
    language: Lang = "ru"


class SqliteUserRepo:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def ensure_user(self, tg_user_id: int) -> User:
        user = await self._get_by_tg_id(tg_user_id)
        if user:
            return user

        await self.conn.execute(
            "INSERT OR IGNORE INTO users (tg_user_id) VALUES (?)",
            (tg_user_id,),
        )
        await self.conn.commit()
        user = await self._get_by_tg_id(tg_user_id)
        assert user is not None
        return user

    async def _get_by_tg_id(self, tg_user_id: int) -> User | None:
        cur = await self.conn.execute(
            "SELECT id, tg_user_id, language FROM users WHERE tg_user_id = ?",
            (tg_user_id,),
        )
        row = await cur.fetchone()
        await cur.close()
        if not row:
            return None

        return User(
            id=row["id"], tg_user_id=row["tg_user_id"], language=row["language"]
        )

    async def get_language(self, tg_user_id: int) -> Lang:
        user = await self.ensure_user(tg_user_id)
        return user.language

    async def set_language(self, tg_user_id: int, lang: Lang) -> None:
        await self.conn.execute(
            "UPDATE users SET language = ? WHERE tg_user_id = ?",
            (lang, tg_user_id),
        )
        await self.conn.commit()

    async def get_by_id(self, user_id: int) -> User | None:
        cur = await self.conn.execute(
            "SELECT id, tg_user_id, language FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cur.fetchone()
        await cur.close()

        if not row:
            return None

        return User(
            id=row["id"], tg_user_id=row["tg_user_id"], language=row["language"]
        )
