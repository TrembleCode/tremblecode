"""Renders the on-disk project skeleton and per-agent workspaces.

Layout under settings.projects_dir/<slug>/ :
  repo/                  git repo; lead workspace (main checkout)
    CLAUDE.md  .mcp.json  .gitignore  .wiki/  .claude/settings.json (ignored)
  worktrees/<agent>/     dev/qa workspaces (git worktrees on agent branches)
  .tremblecode/agents/<name>/identity.md
"""

import json
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import AgentTemplate, Project, ProjectAgent
from . import git_service

_env: Environment | None = None


def jinja() -> Environment:
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(get_settings().templates_dir),
            keep_trailing_newline=True,
        )
    return _env


def project_dirs(project: Project) -> dict[str, Path]:
    base = Path(project.host_dir)
    return {
        "base": base,
        "repo": base / "repo",
        "worktrees": base / "worktrees",
        "state": base / ".tremblecode",
    }


async def roster_for_project(
    session: AsyncSession, project: Project
) -> list[dict]:
    """Expand config_json roster into concrete agent specs (name, role, ...)."""
    templates = {
        t.role_key: t for t in await session.scalars(select(AgentTemplate))
    }
    roster = project.config_json.get("roster", [])
    specs: list[dict] = []
    short_names = {"team_lead": "lead", "backend_dev": "be", "frontend_dev": "fe", "qa": "qa"}
    for entry in roster:
        tpl = templates.get(entry["role_key"])
        if tpl is None:
            continue
        count = entry.get("count", tpl.default_count)
        prefix = short_names.get(tpl.role_key) or tpl.role_key.replace("_", "-")
        for i in range(1, count + 1):
            name = "lead" if tpl.kind == "lead" else f"{prefix}-{i}"
            specs.append(
                {
                    "name": name,
                    "role_key": tpl.role_key,
                    "kind": tpl.kind,
                    "model": entry.get("model") or tpl.model,
                    "effort": entry.get("effort") or tpl.effort,
                    "display_name": tpl.display_name,
                    "description": tpl.description,
                    "system_prompt_md": tpl.system_prompt_md,
                    "template_id": tpl.id,
                }
            )
    return specs


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


async def provision_project_skeleton(
    project: Project, agent_specs: list[dict]
) -> None:
    """Create host dir, repo skeleton, wiki — then git init + initial commit."""
    settings = get_settings()
    dirs = project_dirs(project)
    repo = dirs["repo"]
    repo.mkdir(parents=True, exist_ok=True)
    dirs["worktrees"].mkdir(parents=True, exist_ok=True)
    dirs["state"].mkdir(parents=True, exist_ok=True)

    port_base = project.port_base or settings.port_block_start
    ctx = {
        "project_name": project.name,
        "repo_dir": str(repo),
        "agents": agent_specs,
        "port_base": port_base,
        "port_end": port_base + settings.port_block_size - 1,
        "today": date.today().isoformat(),
    }

    _write(repo / "CLAUDE.md", jinja().get_template("CLAUDE.md.j2").render(ctx))
    _write(
        repo / ".gitignore",
        (settings.templates_dir / "repo_gitignore").read_text(),
    )
    _write(
        repo / ".mcp.json",
        jinja().get_template("mcp.json.j2").render(extra_servers=[]),
    )
    if project.prd_md:
        _write(repo / "PRD.md", project.prd_md)

    wiki = repo / ".wiki"
    _write(wiki / "conventions.md", (settings.templates_dir / "wiki/conventions.md").read_text())
    _write(wiki / "index.md", jinja().get_template("wiki/index.md.j2").render(ctx))
    _write(wiki / "log.md", jinja().get_template("wiki/log.md.j2").render(ctx))
    for page in sorted((settings.templates_dir / "wiki" / "onboarding").glob("*.md")):
        _write(wiki / "onboarding" / page.name, page.read_text())
    (wiki / "pages" / "entities").mkdir(parents=True, exist_ok=True)
    (wiki / "pages" / "decisions").mkdir(parents=True, exist_ok=True)
    (wiki / "pages" / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki / "pages" / "runbooks").mkdir(parents=True, exist_ok=True)

    await git_service.init_repo(repo)


async def provision_agent_workspace(project: Project, agent: ProjectAgent, spec: dict) -> Path:
    """Create the agent's workspace (repo/ for lead, a worktree otherwise),
    its identity file, and its .claude/settings.json (hooks)."""
    dirs = project_dirs(project)
    if spec["kind"] == "lead":
        workspace = dirs["repo"]
    else:
        workspace = dirs["worktrees"] / spec["name"]
        await git_service.create_worktree(
            dirs["repo"], workspace, branch=f"agent/{spec['name']}"
        )

    identity = jinja().get_template("identity.md.j2").render(
        agent_name=spec["name"],
        display_name=spec["display_name"],
        project_name=project.name,
        workspace_path=str(workspace),
        role_prompt=spec["system_prompt_md"],
    )
    _write(dirs["state"] / "agents" / spec["name"] / "identity.md", identity)

    hooks = jinja().get_template("settings.json.j2").render(agent_name=spec["name"])
    # validate the rendered JSON early — a broken hooks file silently disables hooks
    json.loads(hooks)
    _write(workspace / ".claude" / "settings.json", hooks)
    # worktrees don't inherit the repo's .mcp.json checkout? they do (tracked file),
    # but the lead's repo .claude/settings.json is gitignored so each workspace
    # needs its own copy — written above.
    return workspace


def render_mcp_json(project: Project, approved: list) -> None:
    """Re-render repo/.mcp.json with the tremblecode server + approved MCP
    servers. Secret env values are NOT written here — they're injected into
    the tmux session environment; entries reference them as ${KEY}."""
    extra = []
    for suggestion in approved:
        config = {
            "command": suggestion.command,
            "args": suggestion.args,
        }
        if suggestion.env_keys:
            config["env"] = {k: f"${{{k}}}" for k in suggestion.env_keys}
        extra.append({"name": suggestion.name, "config_json": json.dumps(config, indent=2)})
    content = jinja().get_template("mcp.json.j2").render(extra_servers=extra)
    json.loads(content)  # fail fast on template breakage
    _write(project_dirs(project)["repo"] / ".mcp.json", content)
