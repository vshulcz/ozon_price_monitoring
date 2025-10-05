from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


_OZON_RE = re.compile(r"^https?://(www\.)?ozon\.[^/]+/.+", re.IGNORECASE)


def is_ozon_url(url: str) -> bool:
    return bool(_OZON_RE.match(url.strip()))


def parse_price(text: str) -> Decimal | None:
    s = text.strip().replace(" ", "").replace(",", ".")
    try:
        value = Decimal(s)
    except (InvalidOperation, ValueError):
        return None

    if value <= 0:
        return None

    return value.quantize(Decimal("0.01"))
