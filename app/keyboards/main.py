from __future__ import annotations

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.callbacks import MenuCB, SettingsCB
from app.i18n import I18N, Lang


def main_menu_kb(i18n: I18N, lang: Lang | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text=i18n.t(lang, "menu.add"), callback_data=MenuCB(action="add").pack())
    b.button(
        text=i18n.t(lang, "menu.list"),
        callback_data=MenuCB(action="list", page=1).pack(),
    )
    b.button(
        text=i18n.t(lang, "menu.settings"),
        callback_data=MenuCB(action="settings").pack(),
    )
    b.adjust(1)
    return b.as_markup()


def settings_kb(i18n: I18N, lang: Lang | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(
        text=i18n.t(lang, "settings.lang.ru"),
        callback_data=SettingsCB(action="lang", value="ru").pack(),
    )
    b.button(
        text=i18n.t(lang, "settings.lang.en"),
        callback_data=SettingsCB(action="lang", value="en").pack(),
    )
    b.button(
        text=i18n.t(lang, "menu.back"), callback_data=SettingsCB(action="back").pack()
    )
    b.adjust(1, 1, 1)
    return b.as_markup()
