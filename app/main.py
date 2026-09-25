import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, scheduler
from app.api import routes
from app.data import database


@asynccontextmanager
async def lifespan(app):
    database.init_db()
    if not database.is_seeded():
        database.seed()
    task = asyncio.create_task(scheduler.loop())
    yield
    task.cancel()


app = FastAPI(title=config.APP_NAME, lifespan=lifespan)
app.include_router(routes.router)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
