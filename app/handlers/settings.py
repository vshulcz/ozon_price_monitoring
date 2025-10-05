from __future__ import annotations

from aiogram import Router, F
from aiogram.types import CallbackQuery, InaccessibleMessage

from app.callbacks import MenuCB, SettingsCB
from app.i18n import i18n
from app.keyboards.main import main_menu_kb, settings_kb
from app.repositories.users import SqliteUserRepo


router = Router(name="settings")


@router.callback_query(MenuCB.filter(F.action == "settings"))
async def open_settings(cb: CallbackQuery, user_repo: SqliteUserRepo) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    text = f"<b>{i18n.t(user.language, 'settings.title')}</b>\n\n{ i18n.t(user.language, 'settings.choose_lang') }"

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(text, reply_markup=settings_kb(i18n, user.language))
    await cb.answer()


@router.callback_query(SettingsCB.filter(F.action == "lang"))
async def change_lang(
    cb: CallbackQuery, callback_data: SettingsCB, user_repo: SqliteUserRepo
) -> None:
    await user_repo.ensure_user(cb.from_user.id)
    new_lang = (
        (callback_data.value or "ru") if callback_data.value in ("ru", "en") else "ru"
    )
    await user_repo.set_language(cb.from_user.id, new_lang)

    lang_name = "Русский" if new_lang == "ru" else "English"

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(
        i18n.t(new_lang, "settings.lang.changed", lang_name=lang_name),
        reply_markup=main_menu_kb(i18n, new_lang),
    )
    await cb.answer()


@router.callback_query(SettingsCB.filter(F.action == "back"))
async def settings_back(cb: CallbackQuery, user_repo: SqliteUserRepo) -> None:
    lang = await user_repo.get_language(cb.from_user.id)
    text = f"<b>{i18n.t(lang, 'start.title')}</b>\n\n" + i18n.t(lang, "start.body")

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(text, reply_markup=main_menu_kb(i18n, lang))
    await cb.answer()
