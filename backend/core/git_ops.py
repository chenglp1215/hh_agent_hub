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


def clone_or_pull_repo(project: ProjectRegistry, base_dir: str = None) -> git.Repo:
    """Clone or pull a Git repository for the given project.

    If the workspace already exists, attempt a pull. If pull fails,
    remove the workspace and re-clone.
    """
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
