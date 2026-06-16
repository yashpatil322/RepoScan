import os
import tempfile
import shutil
from git import Repo

def clone_repo(github_url: str) -> str:
    """
    Clone a GitHub repository to a temporary directory.
    Returns the path to the cloned repo.
    """
    tmp_dir = tempfile.mkdtemp(prefix="codebase_qa_")
    try:
        print(f"Cloning {github_url} ...")
        Repo.clone_from(github_url, tmp_dir, depth=1)  # depth=1 = shallow clone, faster
        return tmp_dir
    except Exception as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"Failed to clone repo: {e}")


def get_code_files(repo_path: str, extensions: list[str]) -> list[str]:
    """
    Walk the repo directory and return paths of all files
    matching the given extensions.
    """
    code_files = []
    for root, dirs, files in os.walk(repo_path):
        # Skip hidden directories and common non-code dirs
        dirs[:] = [d for d in dirs if not d.startswith('.') 
                   and d not in ('node_modules', '__pycache__', '.git', 'dist', 'build')]
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                code_files.append(os.path.join(root, file))
    return code_files
