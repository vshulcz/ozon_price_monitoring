from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InaccessibleMessage

from app.callbacks import MenuCB
from app.i18n import Lang, i18n
from app.keyboards.main import main_menu_kb
from app.repositories.users import SqliteUserRepo


router = Router(name="start")


def _menu_text(lang: Lang | None) -> str:
    return f"<b>{i18n.t(lang, 'start.title')}</b>\n\n" + i18n.t(lang, "start.body")


@router.message(CommandStart())
async def cmd_start(message: Message, user_repo: SqliteUserRepo) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    user = await user_repo.ensure_user(from_user.id)
    await message.answer(
        _menu_text(user.language),
        reply_markup=main_menu_kb(i18n, user.language),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message, user_repo: SqliteUserRepo) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    user = await user_repo.ensure_user(from_user.id)
    await message.answer(
        (
            f"<b>{i18n.t(user.language, 'start.title')}</b>\n"
            + i18n.t(user.language, "start.body")
        ),
        reply_markup=main_menu_kb(i18n, user.language),
    )


@router.callback_query(MenuCB.filter(F.action == "home"))
async def on_menu_click(
    cb: CallbackQuery, callback_data: MenuCB, user_repo: SqliteUserRepo
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)
    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await cb.message.edit_text(
        _menu_text(user.language), reply_markup=main_menu_kb(i18n, user.language)
    )
    await cb.answer()
