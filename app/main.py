import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app import config, scheduler
from app.api import routes
from app.data import database

DIST_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "dist")
STATIC_DIR = DIST_DIR if os.path.isdir(DIST_DIR) else "static"


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
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
