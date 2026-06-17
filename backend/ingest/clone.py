from __future__ import annotations

"""
clone.py — Git repository cloning and file discovery.

Handles:
- Shallow-cloning a public GitHub repo to a temp directory
- Walking the repo tree to find all supported source code files
- Cleaning up temp directories after ingestion
- Generating a URL-safe repo ID from the GitHub URL
"""

import os
import re
import tempfile
import shutil
from git import Repo, GitCommandError


# Directories to always skip when walking the repo tree
SKIP_DIRS = {
    ".git", ".svn", ".hg",                          # VCS
    "node_modules", "vendor", "venv", ".venv",       # Dependencies
    "__pycache__", ".mypy_cache", ".pytest_cache",   # Caches
    "dist", "build", "out", "target",                # Build output
    ".next", ".nuxt",                                 # Framework output
    "coverage", ".coverage",                          # Test coverage
    ".idea", ".vscode",                               # IDE
    "eggs", "*.egg-info",                             # Python packaging
}

# Max file size to process (500 KB) — skip minified bundles, vendored files, etc.
MAX_FILE_SIZE_BYTES = 500 * 1024


def generate_repo_id(github_url: str) -> str:
    """
    Generate a clean, URL-safe repo ID from a GitHub URL.

    Examples:
        https://github.com/tiangolo/fastapi       → tiangolo-fastapi
        https://github.com/pallets/flask.git       → pallets-flask
        https://github.com/user/my-repo/           → user-my-repo
    """
    url = github_url.rstrip("/")
    # Remove .git suffix if present
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot extract owner/repo from URL: {github_url}")
    owner = parts[-2]
    repo = parts[-1]
    # Sanitize: lowercase, only alphanumeric + hyphens
    repo_id = f"{owner}-{repo}".lower()
    repo_id = re.sub(r"[^a-z0-9\-]", "-", repo_id)
    repo_id = re.sub(r"-+", "-", repo_id).strip("-")
    return repo_id


def clone_repo(github_url: str, clone_dir: str | None = None) -> str:
    """
    Shallow-clone a GitHub repository to a temporary directory.

    Args:
        github_url: Full GitHub URL (https://github.com/owner/repo)
        clone_dir: Optional base directory for cloning. Uses system temp if None.

    Returns:
        Absolute path to the cloned repository.

    Raises:
        RuntimeError: If cloning fails (invalid URL, private repo, network error).
    """
    if clone_dir:
        os.makedirs(clone_dir, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(prefix="reposcan_", dir=clone_dir)
    else:
        tmp_dir = tempfile.mkdtemp(prefix="reposcan_")

    try:
        Repo.clone_from(
            github_url,
            tmp_dir,
            depth=1,           # Shallow clone — only latest commit, much faster
            single_branch=True  # Don't fetch all branches
        )
        return tmp_dir
    except GitCommandError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(
            f"Failed to clone repository '{github_url}'. "
            f"Make sure the URL is correct and the repo is public. "
            f"Git error: {e}"
        )
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Unexpected error cloning repo: {e}")


def get_code_files(repo_path: str, extensions: list[str]) -> list[str]:
    """
    Walk the repository directory tree and collect all source code files
    matching the given extensions.

    Args:
        repo_path: Absolute path to the cloned repository.
        extensions: List of file extensions to include (e.g., [".py", ".js"]).

    Returns:
        List of absolute file paths to source code files.
    """
    code_files = []
    extensions_set = set(extensions)

    for root, dirs, files in os.walk(repo_path):
        # Filter out directories we never want to descend into
        dirs[:] = [
            d for d in dirs
            if d not in SKIP_DIRS and not d.startswith(".")
        ]

        for filename in files:
            # Check extension
            _, ext = os.path.splitext(filename)
            if ext not in extensions_set:
                continue

            filepath = os.path.join(root, filename)

            # Skip files that are too large (likely minified/vendored)
            try:
                if os.path.getsize(filepath) > MAX_FILE_SIZE_BYTES:
                    continue
            except OSError:
                continue

            code_files.append(filepath)

    return sorted(code_files)


def cleanup_repo(repo_path: str) -> None:
    """
    Remove the temporary cloned repository directory.
    Silently ignores errors (e.g., if already removed).
    """
    if repo_path and os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)
