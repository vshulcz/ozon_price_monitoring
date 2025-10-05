from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.i18n import Lang, i18n
from app.repositories.products import ProductsRepo
from app.repositories.users import SqliteUserRepo
from app.services.ozon_client import fetch_product_info
from app.keyboards.products import deal_reached_kb


logger = logging.getLogger(__name__)


async def _notify_deal_reached(
    bot: Bot,
    *,
    user_tg_id: int,
    lang: Lang,
    product_id: int,
    title: str,
    url: str,
    current: float,
    target: float,
):
    text = i18n.t(
        lang,
        "notif.deal_reached",
        title=title,
        current=f"{current:.2f}",
        target=f"{target:.2f}",
    )
    await bot.send_message(
        user_tg_id,
        text,
        reply_markup=deal_reached_kb(i18n, lang, product_id=product_id, url=url),
    )


async def _notify_deal_over(
    bot: Bot,
    *,
    user_tg_id: int,
    lang: Lang,
    title: str,
    current: float,
    target: float,
):
    text = i18n.t(
        lang,
        "notif.deal_over",
        title=title,
        current=f"{current:.2f}",
        target=f"{target:.2f}",
    )
    await bot.send_message(user_tg_id, text, disable_web_page_preview=True)


async def refresh_prices_and_notify(
    bot: Bot, users: SqliteUserRepo, products: ProductsRepo
) -> None:
    async for p in products.list_all_active():
        try:
            info = await fetch_product_info(p.url)
            chosen = info.price_for_compare
            if chosen is None:
                continue

            current = float(chosen)
            await products.update_current_and_history(p.id, current, source="scheduler")

            user = await users.get_by_id(p.user_id)
            if not user:
                continue

            target = float(p.target_price)
            prev_state = p.last_state

            if current <= target:
                if prev_state != "below":
                    await _notify_deal_reached(
                        bot,
                        user_tg_id=user.tg_user_id,
                        lang=user.language,
                        product_id=p.id,
                        title=p.title,
                        url=p.url,
                        current=current,
                        target=target,
                    )
                    await products.set_last_state(
                        p.id, "below", last_notified_price=current
                    )
            else:
                if prev_state == "below":
                    await _notify_deal_over(
                        bot,
                        user_tg_id=user.tg_user_id,
                        lang=user.language,
                        title=p.title,
                        current=current,
                        target=target,
                    )
                    await products.set_last_state(
                        p.id, "above", last_notified_price=None
                    )
        except Exception as e:
            logger.exception("Failed to refresh product %s: %s", p.id, e)


def setup_scheduler(
    bot: Bot, users: SqliteUserRepo, products: ProductsRepo
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        refresh_prices_and_notify,
        CronTrigger(hour="9,15,21", minute=0),
        kwargs={"bot": bot, "users": users, "products": products},
    )
    scheduler.start()
    return scheduler
