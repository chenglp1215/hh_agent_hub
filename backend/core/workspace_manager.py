import json
import os
import shutil
from typing import Dict, Any, Optional
from datetime import datetime
from loguru import logger


class WorkflowWorkspaceManager:
    """工作流工作空间管理器"""

    BASE_PATH = "/data/workflow_workspaces"

    async def setup(self, execution_id: str, repo_url: str = None) -> str:
        """创建工作空间目录"""
        ws = os.path.join(self.BASE_PATH, execution_id)
        os.makedirs(os.path.join(ws, "artifacts"), exist_ok=True)

        if repo_url:
            os.makedirs(os.path.join(ws, "repos"), exist_ok=True)

        context = {
            "execution_id": execution_id,
            "current_stage": 0,
            "status": "running",
            "upstream_summary": [],
            "started_at": datetime.now().isoformat(),
        }
        self._write_context(ws, context)
        logger.info(f"Workspace created: {ws}")
        return ws

    async def stage_transition(self, ws: str, agent_name: str,
                                stage_num: int, result: Dict[str, Any]):
        """更新 context.json 中的阶段信息"""
        context = self._read_context(ws)
        context["current_stage"] = stage_num + 1
        context["upstream_summary"].append({
            "stage": stage_num,
            "agent": agent_name,
            "status": result.get("status", "success"),
            "summary": result.get("summary", ""),
            "artifacts": result.get("artifacts", []),
        })
        self._write_context(ws, context)

    def build_agent_prompt(self, ws: str, agent_config: Dict[str, Any],
                           task_description: str) -> str:
        """构建包含 workspace 上下文的 System Prompt"""
        context = self._read_context(ws)
        summary_text = ""
        for s in context.get("upstream_summary", []):
            summary_text += f"- [{s['agent']}] {s['summary']}\n"
            if s.get("artifacts"):
                summary_text += f"  产出物: {', '.join(s['artifacts'])}\n"

        stage_dir = f"{context['current_stage'] + 1}_{agent_config.get('name', 'unknown')}"

        return f"""## 你的角色
{agent_config.get('system_prompt', '')}

## 当前任务
{task_description}

## 工作空间路径
{ws}

## 上游阶段摘要
{summary_text or '(无，这是第一个阶段)'}

## 工作空间说明
- 上游产物在 {ws}/artifacts/ 目录下
- 你的产出物请写入 {ws}/artifacts/{stage_dir}/
- 完成后生成一个 summary，供下游 Agent 了解进展
"""

    def _read_context(self, ws: str) -> Dict[str, Any]:
        path = os.path.join(ws, "context.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"execution_id": "", "current_stage": 0, "status": "unknown", "upstream_summary": []}

    def _write_context(self, ws: str, context: Dict[str, Any]):
        path = os.path.join(ws, "context.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(context, f, ensure_ascii=False, indent=2)

    async def cleanup(self, execution_id: str):
        """清理工作空间"""
        ws = os.path.join(self.BASE_PATH, execution_id)
        if os.path.exists(ws):
            shutil.rmtree(ws)
            logger.info(f"Workspace cleaned: {ws}")


workspace_manager = WorkflowWorkspaceManager()
