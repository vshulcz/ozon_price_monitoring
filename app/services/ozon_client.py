from __future__ import annotations

import platform
import re
import asyncio
import contextlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional
from urllib.parse import urlparse, urlsplit, urlunsplit

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


FIRST_PARTY = ("ozon.ru", "ozone.ru", "cdn1.ozone.ru", "cdn2.ozone.ru", "ir.ozone.ru")
_PRICE_RE = re.compile(r"(\d[\d\s\u00A0\u2009\u202F]*)\s*₽")


class OzonBlockedError(RuntimeError):
    pass


@dataclass
class ProductInfo:
    title: str
    price_no_card: Optional[Decimal]
    price_with_card: Optional[Decimal]

    @property
    def price_for_compare(self) -> Optional[Decimal]:
        return self.price_with_card or self.price_no_card


def _to_www(u: str) -> str:
    s = urlsplit(u)
    host = s.netloc
    if host.startswith("ozon.ru"):
        host = "www.ozon.ru"
    elif host.endswith(".ozon.ru") and not host.startswith("www."):
        host = "www.ozon.ru"
    return urlunsplit((s.scheme or "https", host, s.path, s.query, s.fragment))


def _normalize_price(text: str) -> Optional[Decimal]:
    if not text:
        return None

    cleaned = (
        text.replace("\u00a0", " ")
        .replace("\u202f", " ")
        .replace("\u2009", " ")
        .replace(" ", "")
        .replace(",", ".")
    )
    m = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    if not m:
        return None
    try:
        return Decimal(m.group(1))
    except Exception:
        return None


class _Browser:
    _pl = None
    _browser: Browser | None = None
    _ctx: BrowserContext | None = None
    _lock = asyncio.Lock()

    @classmethod
    async def ensure_started(cls) -> None:
        if cls._browser:
            return

        async with cls._lock:
            if cls._browser:
                return

            prof = _os_profile()
            cls._pl = await async_playwright().start()

            launch_kwargs = dict(headless=True, args=prof["args"])
            if prof["channel"]:
                try:
                    launch_kwargs["channel"] = prof["channel"]
                    cls._browser = await cls._pl.chromium.launch(**launch_kwargs)
                except Exception:
                    launch_kwargs.pop("channel", None)
                    cls._browser = await cls._pl.chromium.launch(**launch_kwargs)
            else:
                cls._browser = await cls._pl.chromium.launch(**launch_kwargs)

            cls._ctx = await cls._browser.new_context(
                locale="ru-RU",
                user_agent=prof["ua"],
                viewport={"width": 1366, "height": 768},
                java_script_enabled=True,
                color_scheme="light",
                service_workers="block",
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            await cls._ctx.add_init_script(f"""
                Object.defineProperty(navigator, 'webdriver', {{ get: () => undefined }});
                try {{
                  Object.defineProperty(navigator, 'platform', {{ get: () => '{prof["platform_js"]}' }});
                }} catch (e) {{}}
            """)
            await cls._ctx.route("**/*", _route_blocker)

    @classmethod
    async def page(cls) -> Page:
        await cls.ensure_started()
        assert cls._ctx is not None
        page = await cls._ctx.new_page()
        return page

    @classmethod
    async def shutdown(cls) -> None:
        async with cls._lock:
            with contextlib.suppress(Exception):
                if cls._ctx:
                    await cls._ctx.close()
                cls._ctx = None
            with contextlib.suppress(Exception):
                if cls._browser:
                    await cls._browser.close()
                cls._browser = None
            with contextlib.suppress(Exception):
                if cls._pl:
                    await cls._pl.stop()
                cls._pl = None


async def _route_blocker(route, request):
    host = (urlparse(request.url).hostname or "").lower()
    if any(host.endswith(d) for d in FIRST_PARTY):
        return await route.continue_()
    if request.resource_type in {"media"}:
        return await route.abort()
    return await route.continue_()


async def _pass_ozon_challenge(ctx: BrowserContext, page: Page, timeout_ms=45000) -> bool:
    await page.goto("https://www.ozon.ru/?abt_att=1&__rr=1",
                    wait_until="domcontentloaded", timeout=timeout_ms)

    try:
        async with page.expect_response(lambda r: ("www.ozon.ru/abt/result" in r.url) and r.status == 200, timeout=timeout_ms) as resp_info:
            await resp_info.value
    except Exception:
        return False

    cookies = await ctx.cookies("https://www.ozon.ru/")
    ok = any(c.get("name") == "abt_data" for c in cookies)
    return ok


async def _extract_product_info(page: Page) -> ProductInfo:
    await page.wait_for_selector('[data-widget="webProductHeading"] h1', timeout=30000)
    await page.wait_for_selector('[data-widget="webPrice"]', timeout=30000)

    data = await page.evaluate(
        """
        (() => {
          const h1 = document.querySelector('[data-widget="webProductHeading"] h1');
          const title = h1 ? h1.textContent.trim() : '';
          const priceBlock = document.querySelector('[data-widget="webPrice"]');
          const text = priceBlock ? priceBlock.innerText : '';
          return { title, text };
        })()
        """
    )

    title = (data.get("title") or "").strip() or "Ozon товар"
    txt = data.get("text") or ""
    prices = [m.group(1) for m in _PRICE_RE.finditer(txt)]

    with_card = _normalize_price(prices[0]) if len(prices) >= 1 else None
    no_card = _normalize_price(prices[1]) if len(prices) >= 2 else None

    if ("без Ozon Карты" in txt or "without Ozon Card" in txt) and len(prices) >= 2:
        no_card = _normalize_price(prices[1])
    if ("Ozon Карт" in txt or "Ozon Card" in txt) and len(prices) >= 1:
        with_card = _normalize_price(prices[0])

    return ProductInfo(title=title, price_no_card=no_card, price_with_card=with_card)


async def fetch_product_info(
    url: str, *, retries: int = 2, navigation_timeout_ms: int = 60000
) -> ProductInfo:
    if not re.search(r"^https?://(www\.)?ozon\.[^/]+/", url, re.IGNORECASE):
        raise ValueError("Not an Ozon product URL")
    
    url = _to_www(url)

    last_exc: Optional[Exception] = None
    for _ in range(retries + 1):
        page = await _Browser.page()

        try:
            if not await _pass_ozon_challenge(_Browser._ctx, page, timeout_ms=45000):
                raise OzonBlockedError("ozon_antibot_hard_block")

            await page.goto(url, wait_until="domcontentloaded", timeout=navigation_timeout_ms)
            await page.wait_for_url(r"**/product/**", timeout=15000)

            info = await _extract_product_info(page)
            return info

        except Exception as e:
            last_exc = e
            await asyncio.sleep(1.2)
        finally:
            with contextlib.suppress(Exception):
                await page.close()

    assert last_exc is not None
    if isinstance(last_exc, OzonBlockedError):
        raise last_exc

    raise OzonBlockedError(str(last_exc))


async def shutdown_browser() -> None:
    await _Browser.shutdown()


def _os_profile():
    sysname = platform.system()
    if sysname == "Linux":
        return {
            "ua": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "platform_js": "Linux x86_64",
            "args": [
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--lang=ru-RU",
                "--enable-unsafe-swiftshader",
                "--use-gl=swiftshader",
                "--ignore-gpu-blocklist",
            ],
            "channel": None,
        }
    elif sysname == "Darwin":
        return {
            "ua": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "platform_js": "MacIntel",
            "args": ["--lang=ru-RU"],
            "channel": "chrome", 
        }
    else:  # Windows
        return {
            "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "platform_js": "Win32",
            "args": ["--lang=ru-RU"],
            "channel": "chrome", 
        }