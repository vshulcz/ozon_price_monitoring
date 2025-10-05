from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Literal


Lang = Literal["ru", "en"]


@dataclass(frozen=True)
class I18N:
    messages: Dict[str, Dict[str, str]]
    default_lang: Lang = "ru"

    def t(self, lang: Lang | None, key: str, /, **params) -> str:
        lang_key = lang if lang in ("ru", "en") else self.default_lang
        template = self.messages.get(lang_key, {}).get(key)
        if template is None:
            template = self.messages[self.default_lang].get(key, key)
        return template.format(**params)


i18n = I18N(
    messages={
        "ru": {
            # App
            "app.name": "Трекер цен Ozon",
            # Menu
            "menu.add": "➕ Добавить товар",
            "menu.list": "📋 Список товаров",
            "menu.settings": "⚙️ Настройки",
            "menu.back": "🏠 В главное меню",
            # Start
            "start.title": "Привет! Я — бот для отслеживания цен на Ozon.",
            "start.body": (
                "Добавляй товары по ссылке, указывай целевую цену — и я оповещу, когда цена станет выгодной.\n\n"
                "Доступные разделы:\n"
                "• ➕ Добавить товар — начать мастер добавления\n"
                "• 📋 Список товаров — посмотреть и управлять\n"
                "• ⚙️ Настройки — язык и параметры"
            ),
            # Add Product
            "add.title": "Добавление товара",
            "add.ask_url": "Пришлите ссылку на товар Ozon",
            "add.invalid_url": "Кажется, это не ссылка Ozon. Отправьте корректный URL вида https://www.ozon...",
            "add.duplicate": "Этот товар уже добавлен. Вы можете изменить целевую цену из списка товаров.",
            "add.limit_reached": "Достигнут лимит в 10 товаров. Обратитесь к администратору для повышения лимита.",
            "add.found": """Нашёл товар: <b>{title}</b>
Текущая цена: <b>{price}</b>""",
            "add.ask_target": "Укажите целевую цену (число)",
            "add.invalid_price": "Введите корректное положительное число, например: 1999.99",
            "add.saved": """Готово! Товар сохранён.
Название: <b>{title}</b>
Ссылка: {url}
Текущая цена: <b>{current}</b>
Целевая цена: <b>{target}</b>""",
            "add.cancel": "Добавление отменено. Возвращаю в меню.",
            "add.fetching": "Подождите, ищу информацию о товаре на Ozon…",
            "add.fetch_error": "Не удалось получить данные с Ozon. Попробуйте позже.",
            "add.fetch_blocked": "Ozon блокирует доступ (antibot). Попробуйте позже.",
            "add.with_card_label": "С картой",
            "add.no_card_label": "Без карты",
            # List and product card
            "list.title": "Ваши товары (стр. {page}/{pages})",
            "list.empty": 'У вас пока нет товаров. Нажмите "Добавить товар" в главном меню.',
            "list.item": "{title} — {price}",
            "product.title": "Карточка товара",
            "product.name": "Название: <b>{title}</b>",
            "product.link": "Ссылка: {url}",
            "product.curr": "Текущая цена: <b>{price}</b>{date_part}",
            "product.curr.date": " (на {date})",
            "product.target": "Целевая цена: <b>{price}</b>",
            # Edit target
            "edit.ask": "Введите новую целевую цену",
            "edit.saved": "Готово! Целевая цена обновлена: <b>{price}</b>",
            "edit.cancel": "Изменение отменено.",
            # Settings
            "settings.title": "Настройки",
            "settings.choose_lang": "Выберите язык интерфейса:",
            "settings.lang.ru": "🇷🇺 Русский",
            "settings.lang.en": "🇬🇧 English",
            "settings.lang.changed": "Готово! Язык переключён на {lang_name}.",
            # Scheduler / Notifications
            "sched.started": "Планировщик обновления цен запущен (09:00, 21:00).",
            "notif.deal_reached": """🎉 Товар «{title}» достиг целевой цены!
Сейчас: <b>{current}</b> ≤ цель <b>{target}</b>.""",
            "notif.deal_over": """ℹ️ Цена на товар «{title}» снова выше цели.
Сейчас: <b>{current}</b> > цель <b>{target}</b>.""",
            "notif.delete.ok": "Товар удалён и больше не отслеживается.",
            "btn.delete": "🗑️ Удалить товар",
            # Common buttons
            "btn.cancel": "❌ Отмена",
            # Errors
            "error.unexpected": "Упс! Что-то пошло не так. Попробуйте ещё раз позже.",
        },
        "en": {
            # App
            "app.name": "Ozon Price Tracker",
            # Menu
            "menu.add": "➕ Add product",
            "menu.list": "📋 Products",
            "menu.settings": "⚙️ Settings",
            "menu.back": "🏠 Main menu",
            # Start
            "start.title": "Hi! I help you track Ozon product prices.",
            "start.body": (
                "Send a product link and a target price — I'll notify you when the price drops.\n\n"
                "Available sections:\n"
                "• ➕ Add product — start the add wizard\n"
                "• 📋 Products — view & manage\n"
                "• ⚙️ Settings — language & options"
            ),
            # Add Product
            "add.title": "Add product",
            "add.ask_url": "Send an Ozon product link",
            "add.invalid_url": "This doesn't look like an Ozon link. Please send a valid https://www.ozon... URL.",
            "add.duplicate": "This product is already tracked. You can change target price from the list.",
            "add.limit_reached": "You've reached the 10 products limit. Contact admin to increase it.",
            "add.found": """Found: <b>{title}</b>
Current price: <b>{price}</b>""",
            "add.ask_target": "Enter a target price (number)",
            "add.invalid_price": "Please enter a valid positive number, e.g. 1999.99",
            "add.saved": """Done! Product saved.
Title: <b>{title}</b>
Link: {url}
Current price: <b>{current}</b>
Target price: <b>{target}</b>""",
            "add.cancel": "Adding cancelled. Back to menu.",
            "add.fetching": "Fetching product info from Ozon… please wait.",
            "add.fetch_error": "Failed to fetch data from Ozon. Please try again later.",
            "add.fetch_blocked": "Ozon blocked the request (antibot). Please try again later.",
            "add.with_card_label": "With card",
            "add.no_card_label": "Without card",
            # List and product card
            "list.title": "Your products (p. {page}/{pages})",
            "list.empty": 'You have no products yet. Tap "Add product" in main menu.',
            "list.item": "{title} — {price}",
            "product.title": "Product details",
            "product.name": "Title: <b>{title}</b>",
            "product.link": "Link: {url}",
            "product.curr": "Current price: <b>{price}</b>{date_part}",
            "product.curr.date": " (as of {date})",
            "product.target": "Target price: <b>{price}</b>",
            # Edit target
            "edit.ask": "Enter new target price",
            "edit.saved": "Done! Target price updated: <b>{price}</b>",
            "edit.cancel": "Edit cancelled.",
            # Settings
            "settings.title": "Settings",
            "settings.choose_lang": "Choose your language:",
            "settings.lang.ru": "🇷🇺 Russian",
            "settings.lang.en": "🇬🇧 English",
            "settings.lang.changed": "Done! Language set to {lang_name}.",
            # Scheduler / Notifications
            "sched.started": "Price refresh scheduler started (09:00, 21:00).",
            "notif.deal_reached": """🎉 Deal! “{title}” reached the target.
Now: <b>{current}</b> ≤ target <b>{target}</b>.""",
            "notif.deal_over": """ℹ️ “{title}” is no longer below target.
Now: <b>{current}</b> > target <b>{target}</b>.""",
            "notif.delete.ok": "Product removed and will not be tracked anymore.",
            "btn.delete": "🗑️ Remove product",
            # Common buttons
            "btn.cancel": "❌ Cancel",
            # Errors
            "error.unexpected": "Oops! Something went wrong. Please try again later.",
        },
    },
)
