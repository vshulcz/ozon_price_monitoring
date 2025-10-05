from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from typing import Literal


class MenuCB(CallbackData, prefix="menu"):
    action: Literal["home", "add", "list", "settings"]
    page: int | None = None


class SettingsCB(CallbackData, prefix="settings"):
    action: Literal["lang", "back"]
    value: str | None = None  # ru | en


class ActionCB(CallbackData, prefix="action"):
    action: Literal["cancel"]


class ProductCB(CallbackData, prefix="product"):
    action: Literal["open", "edit", "back", "delete"]
    id: int
    page: int | None = None
