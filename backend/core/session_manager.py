import os
import shutil
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from loguru import logger

from config import settings


class SessionManager:
    """Session workspace 生命周期管理

    每个 session 拥有独立的工作空间目录，包含：
    - projects/{project_name}/code/   ← 项目代码（同 session 多 agent 共享）
    - agents/{agent_name}/            ← 各 agent 工作区（artifacts + CLAUDE.md）
    """

    @property
    def base_path(self) -> Path:
        return Path(settings.WORKSPACE_BASE) / "sessions"

    def get_session_path(self, session_id: str) -> Path:
        return self.base_path / session_id

    async def create_workspace(self, session_id: str) -> str:
        """创建 session workspace 目录结构"""
        ws = self.get_session_path(session_id)
        os.makedirs(ws / "projects", exist_ok=True, mode=0o777)
        os.makedirs(ws / "agents", exist_ok=True, mode=0o777)
        os.chmod(str(ws), 0o777)
        logger.info(f"Session workspace created: {ws}")
        return str(ws)

    def get_project_code_path(self, session_id: str, project_name: str) -> str:
        """获取 session 内某项目的代码目录路径"""
        return str(self.get_session_path(session_id) / "projects" / project_name / "code")

    def get_agent_workspace_path(self, session_id: str, agent_name: str) -> str:
        """获取 session 内某 agent 的工作区路径"""
        return str(self.get_session_path(session_id) / "agents" / agent_name)

    def ensure_agent_workspace(self, session_id: str, agent_name: str) -> str:
        """确保 agent 工作区目录存在并返回路径"""
        path = self.get_agent_workspace_path(session_id, agent_name)
        os.makedirs(path, exist_ok=True, mode=0o777)
        return path

    async def cleanup_workspace(self, session_id: str):
        """清理 session workspace（删除整个目录）"""
        ws = self.get_session_path(session_id)
        if ws.exists():
            shutil.rmtree(str(ws), ignore_errors=True)
            logger.info(f"Session workspace cleaned: {ws}")

    async def cleanup_expired(self):
        """清理所有过期 session 的 workspace（定时任务调用）"""
        from models.session import Session

        now = datetime.now()
        expired_sessions = await Session.filter(
            expired_at__lt=now, workspace_path__not_isnull=True
        ).all()

        for s in expired_sessions:
            await self.cleanup_workspace(s.id)
            s.workspace_path = None
            await s.save()

        if expired_sessions:
            logger.info(f"Cleaned workspaces for {len(expired_sessions)} expired sessions")

    async def start_cleanup_task(self, interval_seconds: int = 600):
        """启动定时清理任务（每 interval 秒执行一次）"""
        while True:
            try:
                await self.cleanup_expired()
            except Exception as e:
                logger.warning(f"Session cleanup task error: {e}")
            await asyncio.sleep(interval_seconds)


session_manager = SessionManager()
