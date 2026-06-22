from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    display_name: Optional[str] = None
    description: Optional[str] = None
    role: str = "worker"
    agent_type: str = "local"
    llm_config_id: Optional[int] = None
    llm_config: Optional[Dict[str, Any]] = None
    http_config: Optional[Dict[str, Any]] = None
    claudecode_config: Optional[Dict[str, Any]] = None
    a2a_config: Optional[Dict[str, Any]] = None
    system_prompt: Optional[str] = None
    mcp_links: List[Dict[str, Any]] = []
    kb_ids: List[int] = []
    skill_ids: List[int] = []


class AgentUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    role: Optional[str] = None
    agent_type: Optional[str] = None
    llm_config_id: Optional[int] = None
    llm_config: Optional[Dict[str, Any]] = None
    http_config: Optional[Dict[str, Any]] = None
    claudecode_config: Optional[Dict[str, Any]] = None
    a2a_config: Optional[Dict[str, Any]] = None
    system_prompt: Optional[str] = None
    mcp_links: Optional[List[Dict[str, Any]]] = None
    kb_ids: Optional[List[int]] = None
    skill_ids: Optional[List[int]] = None
    status: Optional[str] = None


class AgentTestRequest(BaseModel):
    message: str = Field(..., min_length=1)
