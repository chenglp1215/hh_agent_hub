import os
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "Multi-Agent Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "agent_platform"
    DB_PASSWORD: str = ""
    DB_NAME: str = "agent_platform"

    USE_SQLITE: bool = False
    SQLITE_PATH: str = ""

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "change-me"
    FERNET_KEY: str = ""
    DEFAULT_RATE_LIMIT: int = 60
    SESSION_TTL: int = 3600
    WORKSPACE_BASE: str = "/data/workflow_workspaces"

    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "./logs/app.log"

    BASE_DIR: Path = Path(__file__).resolve().parent

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

MODELS = [
    "models.sys_config",
    "models.user",
    "models.llm_config",
    "models.agent",
    "models.workflow",
    "models.app",
    "models.session",
    "models.audit_log",
    "models.mcp_server",
    "models.knowledge_base",
    "models.skill",
    "models.project_registry",
    "models.claude_settings",
    "models.chat_log",
    "models.workflow_trace",
    "models.trigger",
]

if settings.USE_SQLITE:
    sqlite_path = settings.SQLITE_PATH or str(settings.BASE_DIR.parent / "test_app.db")
    TORTOISE_ORM = {
        "connections": {
            "default": {
                "engine": "tortoise.backends.sqlite",
                "credentials": {"file_path": sqlite_path},
            }
        },
        "apps": {
            "models": {
                "models": MODELS,
                "default_connection": "default",
            }
        },
        "timezone": "Asia/Shanghai",
    }
else:
    TORTOISE_ORM = {
        "connections": {
            "default": {
                "engine": "tortoise.backends.mysql",
                "credentials": {
                    "host": settings.DB_HOST,
                    "port": settings.DB_PORT,
                    "user": settings.DB_USER,
                    "password": settings.DB_PASSWORD,
                    "database": settings.DB_NAME,
                    "charset": "utf8mb4",
                },
            }
        },
        "apps": {
            "models": {
                "models": MODELS,
                "default_connection": "default",
            }
        },
        "timezone": "Asia/Shanghai",
    }
