from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncGenerator

import aiosqlite


MAX_PRODUCTS_PER_USER = 10
PAGE_SIZE = 5


@dataclass
class Product:
    id: int
    user_id: int
    url: str
    title: str
    target_price: float
    current_price: float | None
    last_notified_price: float | None
    last_state: str | None
    is_active: bool


class ProductsRepo:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def count_by_user(self, user_id: int) -> int:
        cur = await self.conn.execute(
            "SELECT COUNT(*) FROM products WHERE user_id = ?", (user_id,)
        )
        row = await cur.fetchone()
        await cur.close()
        return int(row[0]) if row else 0

    async def list_page(
        self, user_id: int, page: int, page_size: int = PAGE_SIZE
    ) -> tuple[list[Product], int]:
        total = await self.count_by_user(user_id)
        pages = max((total + page_size - 1) // page_size, 1)
        page = max(1, min(page, pages))
        offset = (page - 1) * page_size

        cur = await self.conn.execute(
            "SELECT id, user_id, url, title, target_price, current_price, last_notified_price, last_state, is_active "
            "FROM products WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, page_size, offset),
        )
        rows = await cur.fetchall()
        await cur.close()
        items = [
            Product(
                id=r[0],
                user_id=r[1],
                url=r[2],
                title=r[3],
                target_price=r[4],
                current_price=r[5],
                last_notified_price=r[6],
                last_state=r[7],
                is_active=bool(r[8]),
            )
            for r in rows
        ]
        return items, pages

    async def get_by_url(self, user_id: int, url: str) -> Product | None:
        cur = await self.conn.execute(
            "SELECT id, user_id, url, title, target_price, current_price, last_notified_price, last_state, is_active "
            "FROM products WHERE user_id = ? AND url = ?",
            (user_id, url),
        )
        row = await cur.fetchone()
        await cur.close()

        if not row:
            return None

        return Product(
            id=row[0],
            user_id=row[1],
            url=row[2],
            title=row[3],
            target_price=row[4],
            current_price=row[5],
            last_notified_price=row[6],
            last_state=row[7],
            is_active=bool(row[8]),
        )

    async def get_by_id(self, product_id: int) -> Product | None:
        cur = await self.conn.execute(
            "SELECT id, user_id, url, title, target_price, current_price, last_notified_price, last_state, is_active FROM products WHERE id = ?",
            (product_id,),
        )
        row = await cur.fetchone()
        await cur.close()

        if not row:
            return None

        return Product(
            id=row[0],
            user_id=row[1],
            url=row[2],
            title=row[3],
            target_price=row[4],
            current_price=row[5],
            last_notified_price=row[6],
            last_state=row[7],
            is_active=bool(row[8]),
        )

    async def create(
        self,
        *,
        user_id: int,
        url: str,
        title: str,
        target_price: float,
        current_price: float | None,
    ) -> int:
        cur = await self.conn.execute(
            "INSERT INTO products (user_id, url, title, target_price, current_price) VALUES (?,?,?,?,?)",
            (user_id, url, title, target_price, current_price),
        )
        await self.conn.commit()
        if not isinstance(cur.lastrowid, int):
            return 0

        return int(cur.lastrowid)

    async def add_price_history(
        self, product_id: int, price: float, source: str
    ) -> None:
        await self.conn.execute(
            "INSERT INTO price_history (product_id, price, source) VALUES (?,?,?)",
            (product_id, price, source),
        )
        await self.conn.commit()

    async def get_latest_price(self, product_id: int) -> tuple[float, str] | None:
        cur = await self.conn.execute(
            "SELECT price, observed_at FROM price_history WHERE product_id = ? ORDER BY observed_at DESC LIMIT 1",
            (product_id,),
        )
        row = await cur.fetchone()
        await cur.close()

        if not row:
            return None

        return float(row[0]), str(row[1])

    async def update_target_price(self, product_id: int, new_price: float) -> None:
        await self.conn.execute(
            "UPDATE products SET target_price = ?, updated_at = DATETIME('now') WHERE id = ?",
            (new_price, product_id),
        )
        await self.conn.commit()

    async def list_all_active(self) -> AsyncGenerator[Product]:
        cur = await self.conn.execute(
            "SELECT id, user_id, url, title, target_price, current_price, last_notified_price, last_state, is_active FROM products WHERE is_active = 1",
        )
        rows = await cur.fetchall()
        await cur.close()
        for r in rows:
            yield Product(
                id=r[0],
                user_id=r[1],
                url=r[2],
                title=r[3],
                target_price=r[4],
                current_price=r[5],
                last_notified_price=r[6],
                last_state=r[7],
                is_active=bool(r[8]),
            )

    async def update_current_and_history(
        self, product_id: int, price: float, source: str = "scheduler"
    ) -> None:
        await self.conn.execute(
            "UPDATE products SET current_price = ?, updated_at = DATETIME('now') WHERE id = ?",
            (price, product_id),
        )
        await self.conn.execute(
            "INSERT INTO price_history (product_id, price, source) VALUES (?,?,?)",
            (product_id, price, source),
        )
        await self.conn.commit()

    async def set_last_state(
        self,
        product_id: int,
        state: str | None,
        last_notified_price: float | None,
    ) -> None:
        await self.conn.execute(
            "UPDATE products SET last_state = ?, last_notified_price = ?, updated_at = DATETIME('now') WHERE id = ?",
            (state, last_notified_price, product_id),
        )
        await self.conn.commit()

    async def delete(self, product_id: int) -> None:
        await self.conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await self.conn.commit()
