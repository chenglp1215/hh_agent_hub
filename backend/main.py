from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise import Tortoise
from config import settings, TORTOISE_ORM
from loguru import logger
import secrets
import sys

from core.trigger_scheduler import init_scheduler, shutdown_scheduler
from core.agent_call_log import agent_call_logger  # noqa: F401 — 触发单例初始化
from models.sys_config import SysConfig
from models.user import User
import bcrypt as _bcrypt

logger.remove()
logger.add(sys.stderr, level=settings.LOG_LEVEL)
logger.add(settings.LOG_FILE, rotation="10 MB", retention="7 days", level=settings.LOG_LEVEL)


async def seed_defaults():
    defaults = [
        ("llm.default.provider", "openai", "string", "默认LLM提供商"),
        ("llm.default.model", "gpt-4o-mini", "string", "默认模型"),
        ("llm.default.temperature", "0.3", "number", "默认温度参数"),
        ("system.max_tokens", "4096", "number", "最大token限制"),
        ("system.session_ttl", "3600", "number", "会话过期时间(秒)"),
        ("system.rate_limit.default", "60", "number", "默认限流(次/分钟)"),
        ("wecom.bot_id", "", "secret", "企微智能机器人 Bot ID"),
        ("wecom.bot_secret", "", "secret", "企微智能机器人 Bot Secret"),
    ]
    for key, value, ctype, desc in defaults:
        await SysConfig.get_or_create(
            config_key=key,
            defaults={"config_value": value, "config_type": ctype, "description": desc},
        )

    admin_key = secrets.token_urlsafe(32)
    await User.get_or_create(
        username="admin",
        defaults={
            "password_hash": _bcrypt.hashpw(b"admin123", _bcrypt.gensalt()).decode(),
            "api_key": f"sk-{admin_key}",
            "role": "admin",
            "email": "admin@local.com",
        },
    )
    logger.info("Seed data inserted: admin user and default configs")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Multi-Agent Platform...")
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas(safe=True)
    await seed_defaults()
    await init_scheduler()
    logger.info("Trigger scheduler ready")
    yield
    logger.info("Shutting down...")
    await shutdown_scheduler()
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

from api.middleware import ApiKeyMiddleware

app.add_middleware(ApiKeyMiddleware)

from api.v1 import router as v1_router

app.include_router(v1_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}
