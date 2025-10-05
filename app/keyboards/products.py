from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import MenuCB, ProductCB
from app.i18n import I18N, Lang


def products_list_kb(
    i18n: I18N,
    lang: Lang | None,
    *,
    items: list[tuple[int, str]],
    page: int,
    pages: int,
) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()

    for pid, title in items:
        kb.button(
            text=title, callback_data=ProductCB(action="open", id=pid, page=page).pack()
        )
        kb.adjust(1)

    nav_buttons: list[InlineKeyboardButton] = []
    if page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="◀️", callback_data=MenuCB(action="list", page=page - 1).pack()
            )
        )
    if page < pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="▶️", callback_data=MenuCB(action="list", page=page + 1).pack()
            )
        )
    if nav_buttons:
        kb.row(*nav_buttons)

    kb.row(
        InlineKeyboardButton(
            text=i18n.t(lang, "menu.back"), callback_data=MenuCB(action="home").pack()
        )
    )

    return kb.as_markup()


def product_card_kb(
    i18n: I18N, lang: Lang | None, *, product_id: int, page: int, url: str
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text="✏️ Изменить целевую цену"
        if (lang or "ru") == "ru"
        else "✏️ Edit target price",
        callback_data=ProductCB(action="edit", id=product_id, page=page).pack(),
    )
    b.button(
        text="🗑️ Удалить товар" if (lang or "ru") == "ru" else "🗑️ Remove",
        callback_data=ProductCB(action="delete", id=product_id, page=page).pack(),
    )
    b.button(
        text="⬅️ Назад",
        callback_data=ProductCB(action="back", id=product_id, page=page).pack(),
    )
    b.button(text=i18n.t(lang, "menu.back"), callback_data=MenuCB(action="home").pack())
    b.adjust(1)
    return b.as_markup()


def deal_reached_kb(
    i18n: I18N, lang: Lang | None, *, product_id: int, url: str
) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=i18n.t(lang, "btn.delete"),
        callback_data=ProductCB(action="delete", id=product_id).pack(),
    )
    b.adjust(1)
    return b.as_markup()
