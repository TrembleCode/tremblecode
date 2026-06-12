import json
from pathlib import Path

import pytest

from tremblecode_server.database import SessionLocal
from tremblecode_server.models import Project, ProjectAgent
from tremblecode_server.services import git_service, provisioner


@pytest.fixture
async def project(client, tmp_path):
    res = await client.post(
        "/api/projects", json={"name": "Wiki Proj", "prd_md": "# PRD\nbuild a thing"}
    )
    data = res.json()
    async with SessionLocal() as session:
        project = await session.get(Project, data["id"])
        project.host_dir = str(tmp_path / project.slug)
        project.port_base = 34000
        await session.commit()
        # detach values we need
        session.expunge_all()
    return project


async def test_provision_skeleton_and_workspaces(project):
    async with SessionLocal() as session:
        proj = await session.get(Project, project.id)
        specs = await provisioner.roster_for_project(session, proj)
        assert {s["name"] for s in specs} == {"lead", "be-1", "fe-1", "qa-1"}

        await provisioner.provision_project_skeleton(proj, specs)
        repo = Path(proj.host_dir) / "repo"
        assert (repo / ".git").is_dir()
        assert (repo / "PRD.md").read_text().startswith("# PRD")
        claude_md = (repo / "CLAUDE.md").read_text()
        assert "be-1" in claude_md and "qa-1" in claude_md  # roster table
        assert "34000" in claude_md  # port block
        assert (repo / ".wiki" / "conventions.md").exists()
        assert "Wiki Proj" in (repo / ".wiki" / "index.md").read_text()
        mcp = json.loads((repo / ".mcp.json").read_text())
        assert "tremblecode" in mcp["mcpServers"]

        # lead workspace = repo, dev workspace = worktree on its own branch
        lead_spec = next(s for s in specs if s["kind"] == "lead")
        dev_spec = next(s for s in specs if s["name"] == "be-1")
        lead_agent = ProjectAgent(project_id=proj.id, name="lead", role_key="team_lead")
        dev_agent = ProjectAgent(project_id=proj.id, name="be-1", role_key="backend_dev")

        lead_ws = await provisioner.provision_agent_workspace(proj, lead_agent, lead_spec)
        dev_ws = await provisioner.provision_agent_workspace(proj, dev_agent, dev_spec)
        assert lead_ws == repo
        assert dev_ws == Path(proj.host_dir) / "worktrees" / "be-1"
        assert (dev_ws / "CLAUDE.md").exists()  # worktree sees tracked files

        # hooks settings rendered + valid JSON in both workspaces
        for ws in (lead_ws, dev_ws):
            hooks = json.loads((ws / ".claude" / "settings.json").read_text())
            assert "SessionStart" in hooks["hooks"]

        # identity rendered
        identity = (
            Path(proj.host_dir) / ".tremblecode" / "agents" / "be-1" / "identity.md"
        ).read_text()
        assert "be-1" in identity and "Backend Developer" in identity

        branches = await git_service.list_branches(repo)
        assert "main" in branches and "agent/be-1" in branches

        # idempotent re-provision
        await provisioner.provision_project_skeleton(proj, specs)
        await provisioner.provision_agent_workspace(proj, dev_agent, dev_spec)
