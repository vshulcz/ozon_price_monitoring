# Ozon Price Tracker Bot

A Telegram bot that tracks prices of Ozon products. Users add a product link, set a target price, and the bot checks prices three times a day and notifies when the target is reached.


## Run

Prepare .env (set BOT_TOKEN).

### Locally

```sh
uv sync && source .venv/bin/activate
python -m playwright install chromium
python -m app.bot
```

### Docker

```sh
docker compose up --build -d
```

## Usage Flow

1. Tap Add product and send a valid Ozon product URL.
2. The bot fetches product title and current price.
3. Enter a target price.
4. The product is stored and appears in Products. You can open its card and Edit target price, Open Ozon, or go Back.
5. The scheduler runs at 09:00, 15:00 and 21:00 (server time) and updates prices, storing history.
6. When current ≤ target, you receive a deal reached notification with a Remove product button.
7. If later current > target, you receive one deal over notification. Repeated notifications for the same state are suppressed.

## Internationalization

* RU 🇷🇺 and EN 🇬🇧 message dictionaries live in app/i18n.py.
* In bot: settings → choose language.

## Notes

* Scraping may be against Ozon’s terms; use responsibly and at your own risk.
* SQLite is sufficient for small deployments; you can swap to Postgres by replacing aiosqlite repos.