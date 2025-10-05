from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import ActionCB
from app.i18n import I18N, Lang


def cancel_kb(i18n: I18N, lang: Lang | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=i18n.t(lang, "btn.cancel"), callback_data=ActionCB(action="cancel").pack()
    )
    return b.as_markup()
