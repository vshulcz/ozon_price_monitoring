from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from app.config import Settings
from app.db import init_db
from app.handlers import start as start_handlers
from app.handlers import settings as settings_handlers
from app.handlers import add_product as add_handlers
from app.handlers import products as products_handlers
from app.middlewares.errors import ErrorsMiddleware
from app.repositories.products import ProductsRepo
from app.repositories.users import SqliteUserRepo
from app.scheduler import setup_scheduler
from app.services.ozon_client import shutdown_browser


class DIRepositoryMiddleware:
    def __init__(
        self, *, user_repo: SqliteUserRepo, products_repo: ProductsRepo
    ) -> None:
        self.user_repo = user_repo
        self.products_repo = products_repo

    async def __call__(self, handler, event, data):
        data["user_repo"] = self.user_repo
        data["products"] = self.products_repo
        return await handler(event, data)


async def setup_bot_commands(bot: Bot) -> None:
    cmds = [
        BotCommand(command="start", description="Start / Запуск"),
        BotCommand(command="menu", description="Main menu / Главное меню"),
    ]
    await bot.set_my_commands(cmds)


async def main() -> None:
    settings = Settings.from_env()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    conn = await init_db(settings.database_path)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    user_repo = SqliteUserRepo(conn)
    products_repo = ProductsRepo(conn)

    dp.message.middleware(ErrorsMiddleware(user_repo))
    dp.callback_query.middleware(ErrorsMiddleware(user_repo))

    di_mw = DIRepositoryMiddleware(user_repo=user_repo, products_repo=products_repo)
    dp.message.middleware(di_mw)
    dp.callback_query.middleware(di_mw)

    dp.include_router(start_handlers.router)
    dp.include_router(settings_handlers.router)
    dp.include_router(add_handlers.router)
    dp.include_router(products_handlers.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)

    scheduler = setup_scheduler(bot, user_repo, products_repo)

    logging.info("Bot started. Polling with scheduler...")
    try:
        await dp.start_polling(bot)
    finally:
        with suppress(Exception):
            scheduler.shutdown(wait=False)
        with suppress(Exception):
            await bot.session.close()
        with suppress(Exception):
            await shutdown_browser()
        with suppress(Exception):
            await conn.close()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
