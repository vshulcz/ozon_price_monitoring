from __future__ import annotations

import re
import asyncio
import contextlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


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

            cls._pl = await async_playwright().start()
            cls._browser = await cls._pl.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-background-timer-throttling",
                    "--disable-breakpad",
                    "--disable-client-side-phishing-detection",
                    "--disable-default-apps",
                    "--disable-features=site-per-process,Translate",
                    "--disable-hang-monitor",
                    "--disable-popup-blocking",
                    "--disable-prompt-on-repost",
                    "--disable-renderer-backgrounding",
                    "--force-color-profile=srgb",
                    "--metrics-recording-only",
                    "--no-first-run",
                    "--no-zygote",
                    "--mute-audio",
                    "--password-store=basic",
                    "--use-mock-keychain",
                ],
            )
            cls._ctx = await cls._browser.new_context(
                locale="ru-RU",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1200, "height": 800},
                java_script_enabled=True,
                color_scheme="light",
                timezone_id="Europe/Moscow",
                extra_http_headers={
                    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                },
            )
            await cls._ctx.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = window.chrome || { runtime: {} };
                Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
                Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
                Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] });
                const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
                if (originalQuery) {
                  window.navigator.permissions.query = (parameters) => (
                    parameters && parameters.name === 'notifications'
                      ? Promise.resolve({ state: Notification.permission })
                      : originalQuery(parameters)
                  );
                }
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                  if (parameter === 37445) return 'Intel Inc.';
                  if (parameter === 37446) return 'Intel Iris OpenGL Engine';
                  return getParameter.call(this, parameter);
                };
                """
            )
            await cls._ctx.route("**/*", _route_blocker)

    @classmethod
    async def page(cls) -> Page:
        await cls.ensure_started()
        assert cls._ctx is not None
        return await cls._ctx.new_page()

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
    url = request.url
    rt = request.resource_type

    if "abt-challenge" in url or "abt-complaints" in url or "cdn2.ozone.ru" in url:
        return await route.continue_()

    if rt in {"image", "media", "font"}:
        return await route.abort()

    if "ir.ozone.ru/s3/multimedia" in url:
        return await route.abort()

    return await route.continue_()


async def _passed_challenge(page: Page) -> bool:
    u = page.url or ""
    if "abt-challenge" in u:
        return False
    el = await page.query_selector('[data-widget="webProductHeading"] h1')
    return el is not None


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

    last_exc: Optional[Exception] = None
    for _ in range(retries + 1):
        page = await _Browser.page()
        try:
            await page.goto(
                url, wait_until="networkidle", timeout=navigation_timeout_ms
            )

            for _ in range(3):
                if await _passed_challenge(page):
                    break
                await page.wait_for_timeout(1500)
                await page.reload(wait_until="networkidle")
            else:
                await page.goto(
                    url, wait_until="networkidle", timeout=navigation_timeout_ms
                )
                if not await _passed_challenge(page):
                    raise OzonBlockedError("ozon_antibot_blocked_after_js")

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
