from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from config import settings, TORTOISE_ORM
from loguru import logger
import sys

logger.remove()
logger.add(sys.stderr, level=settings.LOG_LEVEL)
logger.add(settings.LOG_FILE, rotation="10 MB", retention="7 days", level=settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Multi-Agent Platform...")
    await Tortoise.init(config=TORTOISE_ORM)
    logger.info("Database connected")
    yield
    logger.info("Shutting down...")
    await Tortoise.close_connections()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from api.v1 import router as v1_router

app.include_router(v1_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
