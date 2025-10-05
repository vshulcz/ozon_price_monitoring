from __future__ import annotations

import json
import platform
import re
import asyncio
import contextlib
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote, urlparse, urlsplit, urlunsplit

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


FIRST_PARTY = ("ozon.ru", "ozone.ru", "cdn1.ozone.ru", "cdn2.ozone.ru", "ir.ozone.ru")
_WIDGET_PRICE_KEYS = ("webPrice", "webProductPrices", "webSale")
_WIDGET_TITLE_KEYS = ("webProductHeading",)


class OzonBlockedError(RuntimeError):
    pass


@dataclass
class ProductInfo:
    title: str
    price_no_card: Decimal | None
    price_with_card: Decimal | None

    @property
    def price_for_compare(self) -> Decimal | None:
        return self.price_with_card or self.price_no_card


def _to_www(u: str) -> str:
    s = urlsplit(u)
    host = s.netloc
    if host.startswith("ozon.ru"):
        host = "www.ozon.ru"
    elif host.endswith(".ozon.ru") and not host.startswith("www."):
        host = "www.ozon.ru"
    return urlunsplit((s.scheme or "https", host, s.path, s.query, s.fragment))


def _normalize_price(text: str) -> Decimal | None:
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


async def _pass_ozon_challenge(
    ctx: BrowserContext, page: Page, timeout_ms=45000
) -> bool:
    await page.goto(
        "https://www.ozon.ru/?abt_att=1&__rr=1",
        wait_until="domcontentloaded",
        timeout=timeout_ms,
    )

    try:
        async with page.expect_response(
            lambda r: ("www.ozon.ru/abt/result" in r.url) and r.status == 200,
            timeout=timeout_ms,
        ) as resp_info:
            await resp_info.value
    except Exception:
        return False

    cookies = await ctx.cookies("https://www.ozon.ru/")
    ok = any(c.get("name") == "abt_data" for c in cookies)
    return ok


async def fetch_product_info(url: str, *, retries: int = 2) -> ProductInfo:
    if not re.search(r"^https?://(www\.)?ozon\.[^/]+/", url, re.IGNORECASE):
        raise ValueError("Not an Ozon product URL")

    url = _to_www(url)

    for _ in range(retries + 1):
        page = await _Browser.page()
        try:
            return await fetch_product_info_via_api(url)
        except Exception:
            await asyncio.sleep(1.2)
        finally:
            with contextlib.suppress(Exception):
                await page.close()

    raise OzonBlockedError()


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


def _iter_widget_objs(widget_states: dict[str, str]):
    for k, v in (widget_states or {}).items():
        if not isinstance(v, str):
            continue
        with contextlib.suppress(Exception):
            yield k, json.loads(v)


def _is_price_widget(key: str) -> bool:
    low = key.lower()
    return any(name.lower() in low for name in _WIDGET_PRICE_KEYS)


def _is_title_widget(key: str) -> bool:
    low = key.lower()
    return any(name.lower() in low for name in _WIDGET_TITLE_KEYS)


def _pick_title(data: dict) -> str | None:
    for k, obj in _iter_widget_objs(data.get("widgetStates") or {}):
        if _is_title_widget(k):
            t = obj.get("title")
            if isinstance(t, str) and t.strip():
                return t.strip()
    with contextlib.suppress(Exception):
        t = (data.get("seo") or {}).get("title")
        if t and isinstance(t, str) and t.strip():
            return t.strip()
    for _, obj in _iter_widget_objs(data.get("widgetStates") or {}):
        with contextlib.suppress(Exception):
            t = (obj.get("cellTrackingInfo") or {}).get("product", {}).get("title") or (
                obj.get("product") or {}
            ).get("title")
            if t and isinstance(t, str) and t.strip():
                return t.strip()
    return None


def _pick_prices(data: dict) -> tuple[Decimal | None, Decimal | None]:
    with_card = None
    no_card = None

    for k, obj in _iter_widget_objs(data.get("widgetStates") or {}):
        if not _is_price_widget(k):
            continue

        is_avail = obj.get("isAvailable", True)

        cand_card = obj.get("cardPrice")
        cand_no = obj.get("price")
        if cand_card is None and cand_no is None:
            product = (obj.get("cellTrackingInfo") or {}).get("product", {}) or obj.get(
                "product", {}
            )
            cand_card = (
                cand_card or product.get("cardPrice") or product.get("finalPrice")
            )
            cand_no = cand_no or product.get("price") or product.get("originalPrice")

        wc = (
            _normalize_price(str(cand_card))
            if isinstance(cand_card, str)
            else (_normalize_price(str(cand_card)) if cand_card is not None else None)
        )
        nc = (
            _normalize_price(str(cand_no))
            if isinstance(cand_no, str)
            else (_normalize_price(str(cand_no)) if cand_no is not None else None)
        )

        if wc and (not with_card or is_avail):
            with_card = wc
        if nc and (not no_card or is_avail):
            no_card = nc

        if with_card and no_card:
            break

    if not (with_card and no_card):
        dump = json.dumps(data, ensure_ascii=False)
        prices = [
            _normalize_price(m)
            for m in re.findall(r"(\d[\d\s\u00A0\u2009\u202F]*)\s*₽", dump)
        ]
        prices = [p for p in prices if p]
        if prices:
            if not with_card and len(prices) >= 1:
                with_card = prices[0]
            if not no_card and len(prices) >= 2:
                no_card = prices[1]

    return with_card, no_card


async def _ozon_api_get_json_v2(ctx, url: str) -> dict | None:
    s = urlsplit(url)
    path_q = s.path + (("?" + s.query) if s.query else "")
    q = quote(path_q, safe="/:?=&%")
    api_url = f"https://api.ozon.ru/composer-api.bx/page/json/v2?url={q}"
    headers = {
        "Accept": "application/json",
        "Referer": "https://www.ozon.ru/",
    }
    r = await ctx.request.get(api_url, headers=headers)
    if not r.ok:
        return None
    with contextlib.suppress(Exception):
        return await r.json()
    return None


async def fetch_product_info_via_api(url: str) -> ProductInfo:
    await _Browser.ensure_started()
    ctx = _Browser._ctx
    assert ctx is not None

    with contextlib.suppress(Exception):
        page = await ctx.new_page()
        try:
            await _pass_ozon_challenge(ctx, page, timeout_ms=20000)
        finally:
            await page.close()

    data = await _ozon_api_get_json_v2(ctx, _to_www(url))
    if not data:
        raise OzonBlockedError("ozon_api_empty")

    title = _pick_title(data) or "Ozon item"
    with_card, no_card = _pick_prices(data)

    return ProductInfo(title=title, price_with_card=with_card, price_no_card=no_card)
