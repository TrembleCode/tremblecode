import asyncio
import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60
    )
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


async def run_git(args: list[str], cwd: Path) -> str:
    return await asyncio.to_thread(_run, args, cwd)


async def init_repo(repo_dir: Path) -> None:
    """Initialize the project repo with whatever the provisioner already wrote."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    if (repo_dir / ".git").exists():
        return
    await run_git(["init", "-b", "main"], repo_dir)
    await run_git(["config", "user.name", "TrembleCode"], repo_dir)
    await run_git(["config", "user.email", "agents@tremblecode.local"], repo_dir)
    await run_git(["add", "-A"], repo_dir)
    await run_git(["commit", "-m", "chore: project skeleton", "--allow-empty"], repo_dir)


async def create_worktree(repo_dir: Path, worktree_path: Path, branch: str) -> None:
    """Create a worktree on its own agent branch (worktrees need distinct branches)."""
    if worktree_path.exists():
        return
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        await run_git(
            ["worktree", "add", "-b", branch, str(worktree_path), "main"], repo_dir
        )
    except GitError:
        # branch may already exist from a previous provision
        await run_git(["worktree", "add", str(worktree_path), branch], repo_dir)


async def list_branches(repo_dir: Path) -> list[str]:
    out = await run_git(["branch", "--format=%(refname:short)"], repo_dir)
    return [b for b in out.splitlines() if b]
