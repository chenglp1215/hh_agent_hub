from pydantic import BaseModel, Field
from typing import Optional


class ProjectRegistryCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    display_name: Optional[str] = None
    description: Optional[str] = None
    git_repo_url: str = Field(..., max_length=500)
    git_branch: str = "main"
    git_auth_username: Optional[str] = None
    git_auth_token: Optional[str] = None
    clone_path: Optional[str] = None
    system_prompt: Optional[str] = None
    fix_timeout_minutes: int = 30


class ProjectRegistryUpdate(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_auth_username: Optional[str] = None
    git_auth_token: Optional[str] = None
    clone_path: Optional[str] = None
    system_prompt: Optional[str] = None
    fix_timeout_minutes: Optional[int] = None
    status: Optional[str] = None
