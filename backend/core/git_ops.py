import os
import shutil
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from typing import Optional

import git
from loguru import logger

from models.project_registry import ProjectRegistry


def embed_token_in_url(repo_url: str, token: str, username: str = None) -> str:
    """Embed auth token into Git URL for authentication."""
    parsed = urlparse(repo_url)
    if not token:
        return repo_url
    if username:
        netloc = f"{username}:{token}@{parsed.netloc}"
    else:
        netloc = f"{token}@{parsed.netloc}"
    return urlunparse((parsed.scheme, netloc, parsed.path, "", "", ""))


def get_workspace_path(project: ProjectRegistry, base_dir: str = None) -> Path:
    """Determine the workspace directory for a project.

    If project.clone_path is set, use it as the parent directory.
    Otherwise, use $CWD/workspaces/ as the base.
    """
    if project.clone_path:
        return Path(project.clone_path) / project.name
    base = base_dir or os.path.join(os.getcwd(), "workspaces")
    return Path(base) / project.name


def clone_or_pull_repo(project: ProjectRegistry, base_dir: str = None,
                       target_path: str = None) -> git.Repo:
    """Clone or pull a Git repository for the given project.

    If the workspace already exists, attempt a pull. If pull fails,
    remove the workspace and re-clone.

    Args:
        project: 项目注册表记录（含 repo URL、认证等）
        base_dir: 代码目录的父目录（与 target_path 二选一）
        target_path: 精确的目标代码目录路径（与 base_dir 二选一）

    Returns:
        git.Repo 对象
    """
    if target_path:
        workspace_path = Path(target_path)
    else:
        workspace_path = get_workspace_path(project, base_dir)
    repo_url = project.git_repo_url

    if not repo_url.endswith(".git"):
        repo_url = repo_url.rstrip("/") + ".git"

    auth_url = embed_token_in_url(repo_url, project.git_auth_token or "", project.git_auth_username)

    try:
        if workspace_path.exists():
            try:
                logger.info(f"Workspace exists, pulling: {workspace_path}")
                repo = git.Repo(workspace_path)
                repo.remotes.origin.pull()
                logger.info(f"Pull completed for {repo_url}")
                return repo
            except Exception as pull_error:
                logger.warning(f"Pull failed ({pull_error}), removing workspace and re-cloning")
                shutil.rmtree(workspace_path, ignore_errors=True)

        logger.info(f"Cloning repo: {repo_url} to {workspace_path}")
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        repo = git.Repo.clone_from(auth_url, workspace_path, branch=project.git_branch)
        logger.info(f"Clone completed, checked out {project.git_branch}")
        return repo

    except git.exc.GitCommandError as e:
        logger.error(f"Git command failed: {e.stderr}")
        raise RuntimeError(f"Git operation failed: {e.stderr}")
    except Exception as e:
        logger.error(f"Git operation error: {type(e).__name__}: {e}")
        raise


def ensure_code_exists(project: ProjectRegistry, target_path: str,
                       force_pull: bool = False) -> bool:
    """确保项目代码在 target_path 存在。

    Args:
        project: 项目注册表记录
        target_path: 期望的代码目录（如 session_workspace/projects/{name}/code/）
        force_pull: 是否强制拉取最新代码

    Returns:
        True 表示代码就绪（已存在或已克隆），False 表示没有配置 repo URL
    """
    if not project.git_repo_url:
        logger.info(f"Project {project.name} has no git repo URL, skipping clone")
        return False

    code_dir = Path(target_path)
    already_exists = code_dir.exists()

    if not already_exists:
        # 首次 clone
        code_dir.parent.mkdir(parents=True, exist_ok=True)
        clone_or_pull_repo(project, target_path=str(target_path))
        logger.info(f"Cloned {project.name} to {target_path}")
        return True

    # 已存在：按需 pull
    if force_pull:
        try:
            repo = git.Repo(code_dir)
            repo.remotes.origin.pull()
            logger.info(f"Pulled latest for {project.name} at {target_path}")
        except Exception as e:
            logger.warning(f"Pull failed ({e}), code exists at {target_path}, continuing with existing")
        return True

    logger.info(f"Code exists at {target_path}, skipping git operations")
    return True
