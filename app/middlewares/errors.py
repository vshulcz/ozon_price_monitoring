from __future__ import annotations

import logging
from typing import Optional

from aiogram.types import Message, CallbackQuery, User

from app.i18n import i18n
from app.repositories.users import SqliteUserRepo


logger = logging.getLogger(__name__)


class ErrorsMiddleware:
    def __init__(self, user_repo: Optional[SqliteUserRepo] = None) -> None:
        self.user_repo = user_repo

    async def __call__(self, handler, event, data):
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Unhandled error")

        lang = "ru"
        try:
            repo: Optional[SqliteUserRepo] = data.get("user_repo") or self.user_repo
            user_id = None
            if isinstance(event, Message | CallbackQuery) and isinstance(
                event.from_user, User
            ):
                user_id = event.from_user.id
            if repo and user_id:
                lang = (await repo.ensure_user(user_id)).language
        except Exception:
            pass

        text = i18n.t(lang, "error.unexpected")
        try:
            if isinstance(event, CallbackQuery):
                await event.answer("Error", show_alert=False)

                if isinstance(event.message, Message):
                    await event.message.answer(text)

            elif isinstance(event, Message):
                await event.answer(text)
        except Exception:
            pass

        return None
