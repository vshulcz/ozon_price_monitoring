from __future__ import annotations

from decimal import Decimal

from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InaccessibleMessage

from app.callbacks import MenuCB, ActionCB
from app.i18n import i18n
from app.keyboards.common import cancel_kb
from app.keyboards.main import main_menu_kb
from app.repositories.products import ProductsRepo, MAX_PRODUCTS_PER_USER
from app.repositories.users import SqliteUserRepo
from app.services.ozon_client import fetch_product_info
from app.utils.validators import is_ozon_url, parse_price


router = Router(name="add_product")


class AddProduct(StatesGroup):
    waiting_for_url = State()
    waiting_for_target_price = State()


@router.callback_query(MenuCB.filter(F.action == "add"))
async def start_add(
    cb: CallbackQuery,
    user_repo: SqliteUserRepo,
    products: ProductsRepo,
    state: FSMContext,
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    count = await products.count_by_user(user.id)
    if count >= MAX_PRODUCTS_PER_USER:
        await cb.message.edit_text(
            i18n.t(user.language, "add.limit_reached"),
            reply_markup=main_menu_kb(i18n, user.language),
        )
        await cb.answer()
        return

    await state.clear()
    await state.set_state(AddProduct.waiting_for_url)
    await cb.message.edit_text(
        f"<b>{i18n.t(user.language, 'add.title')}</b>\n\n{ i18n.t(user.language, 'add.ask_url') }",
        reply_markup=cancel_kb(i18n, user.language),
    )
    await cb.answer()


@router.callback_query(ActionCB.filter(F.action == "cancel"))
async def add_cancel(
    cb: CallbackQuery, user_repo: SqliteUserRepo, state: FSMContext
) -> None:
    user = await user_repo.ensure_user(cb.from_user.id)

    if isinstance(cb.message, InaccessibleMessage | None):
        return

    await state.clear()
    await cb.message.edit_text(
        i18n.t(user.language, "add.cancel"),
        reply_markup=main_menu_kb(i18n, user.language),
    )
    await cb.answer()


@router.message(AddProduct.waiting_for_url)
async def got_url(
    message: Message,
    user_repo: SqliteUserRepo,
    products: ProductsRepo,
    state: FSMContext,
) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    user = await user_repo.ensure_user(from_user.id)
    url = (message.text or "").strip()

    if not is_ozon_url(url):
        await message.answer(
            i18n.t(user.language, "add.invalid_url"),
            reply_markup=cancel_kb(i18n, user.language),
        )
        return

    existing = await products.get_by_url(user.id, url)
    if existing:
        await message.answer(
            i18n.t(user.language, "add.duplicate"),
            reply_markup=main_menu_kb(i18n, user.language),
        )
        await state.clear()
        return
    
    waiting_text = i18n.t(user.language, "add.fetching")
    temp_msg = await message.answer(waiting_text, reply_markup=cancel_kb(i18n, user.language))

    await state.update_data(temp_message_chat_id=temp_msg.chat.id, temp_message_id=temp_msg.message_id)

    try:
        info = await fetch_product_info(url)
    except RuntimeError:
        err_text = i18n.t(user.language, "add.fetch_blocked")
        try:
            if (await state.get_state()) == AddProduct.waiting_for_url.state:
                await temp_msg.edit_text(err_text, reply_markup=cancel_kb(i18n, user.language))
        except Exception:
            await message.answer(err_text, reply_markup=cancel_kb(i18n, user.language))
        return
    except Exception:
        err_text = i18n.t(user.language, "add.fetch_error")
        try:
            if (await state.get_state()) == AddProduct.waiting_for_url.state:
                await temp_msg.edit_text(err_text, reply_markup=cancel_kb(i18n, user.language))
        except Exception:
            await message.answer(err_text, reply_markup=cancel_kb(i18n, user.language))
        return
    
    if (await state.get_state()) != AddProduct.waiting_for_url.state:
        return

    chosen = info.price_with_card or info.price_no_card
    await state.update_data(
        url=url,
        title=info.title,
        current_price=str(chosen) if chosen is not None else None,
    )

    lines = [
        i18n.t(
            user.language, "add.found", title=info.title, price=f"{(chosen or 0):.2f}"
        )
    ]
    if info.price_with_card is not None:
        lines.append(f"\n{ i18n.t(user.language, 'add.with_card_label') }: <b>{info.price_with_card:.2f}</b>")
    if info.price_no_card is not None:
        lines.append(f"{ i18n.t(user.language, 'add.no_card_label') }: <b>{info.price_no_card:.2f}</b>")

    ftext = "\n".join(lines)
    try:
        await temp_msg.edit_text(ftext)
    except Exception:
        await message.answer(ftext)

    await state.set_state(AddProduct.waiting_for_target_price)
    await message.answer(
        i18n.t(user.language, "add.ask_target"),
        reply_markup=cancel_kb(i18n, user.language),
    )


@router.message(AddProduct.waiting_for_target_price)
async def got_target_price(
    message: Message,
    user_repo: SqliteUserRepo,
    products: ProductsRepo,
    state: FSMContext,
) -> None:
    from_user = message.from_user
    if from_user is None:
        return

    user = await user_repo.ensure_user(from_user.id)

    price = parse_price(message.text or "")
    if price is None:
        await message.answer(
            i18n.t(user.language, "add.invalid_price"),
            reply_markup=cancel_kb(i18n, user.language),
        )
        return

    data = await state.get_data()
    url: str = data["url"]
    title: str = data["title"]
    current_price = Decimal(data["current_price"]) if "current_price" in data else None

    product_id = await products.create(
        user_id=user.id,
        url=url,
        title=title,
        target_price=float(price),
        current_price=float(current_price) if current_price is not None else None,
    )

    if current_price is not None:
        await products.add_price_history(product_id, float(current_price), source="add")

    await state.clear()
    await message.answer(
        i18n.t(
            user.language,
            "add.saved",
            title=title,
            url=url,
            current=f"{current_price:.2f}" if current_price is not None else "—",
            target=f"{price:.2f}",
        ),
        reply_markup=main_menu_kb(i18n, user.language),
    )
