from contextlib import asynccontextmanager

from fastapi import FastAPI

import db
import handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    try:
        yield
    finally:
        await db.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    handlers.attach(app)
    return app


app = create_app()
