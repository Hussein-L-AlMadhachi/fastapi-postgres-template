from db import DB
from model.items.dto import Item
import asyncpg


class ItemsService:
    db: DB

    def __init__(self, conn: asyncpg.Connection):
        self.db = DB(conn)

    async def create(self, item: Item) -> int:
        row = await self.db.insert("items", item.model_dump())
        return row["id"]

    async def listAll(self) -> list[dict]:
        return await self.db.fetchAll("SELECT * FROM items ORDER BY id")

    async def fetch(self, item_id: int) -> dict | None:
        return await self.db.fetchOne("SELECT * FROM items WHERE id = $1", item_id)
