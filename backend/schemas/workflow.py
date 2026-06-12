from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    flow_type: str = Field(..., pattern="^(supervisor|sequential)$")
    supervisor_agent_id: Optional[int] = None
    worker_agent_ids: List[int] = []
    edges: List[Dict[str, Any]] = []
    parallel_groups: List[Dict[str, Any]] = []
    human_interrupts: List[Dict[str, Any]] = []
    error_strategy: str = "fail_fast"
    agent_timeout_seconds: int = 60
    workflow_timeout_seconds: int = 300
    max_retries: int = 2


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    flow_type: Optional[str] = None
    supervisor_agent_id: Optional[int] = None
    worker_agent_ids: Optional[List[int]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    parallel_groups: Optional[List[Dict[str, Any]]] = None
    human_interrupts: Optional[List[Dict[str, Any]]] = None
    error_strategy: Optional[str] = None
    agent_timeout_seconds: Optional[int] = None
    workflow_timeout_seconds: Optional[int] = None
    max_retries: Optional[int] = None
    status: Optional[str] = None


class InterruptResolve(BaseModel):
    action: str = Field(..., pattern="^(approve|reject)$")
    comment: Optional[str] = None
