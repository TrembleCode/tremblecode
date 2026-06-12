import json

from tremblecode_server.config import get_settings
from tremblecode_server.database import SessionLocal
from tremblecode_server.models import Project

HEADERS = {"X-Tremblecode-Secret": get_settings().internal_secret}


async def _make_project(client, tmp_path):
    res = await client.post(
        "/api/projects", json={"name": "CmwTest", "prd_md": "# PRD"}
    )
    pid = res.json()["id"]
    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        project.host_dir = str(tmp_path / "cmw")
        project.port_base = 34200
        await session.commit()

    from tremblecode_server.models import AgentState, ProjectAgent
    from tremblecode_server.services import provisioner

    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        specs = await provisioner.roster_for_project(session, project)
        await provisioner.provision_project_skeleton(project, specs)
        for spec in specs:
            if spec["kind"] != "lead":
                continue
            agent = ProjectAgent(
                project_id=pid,
                name=spec["name"],
                role_key=spec["role_key"],
                kind=spec["kind"],
                model=spec["model"],
                state=AgentState.IDLE,
            )
            agent.workspace_path = str(
                await provisioner.provision_agent_workspace(project, agent, spec)
            )
            session.add(agent)
        await session.commit()
    return pid


async def test_cost_ingestion_idempotent(client, tmp_path):
    pid = await _make_project(client, tmp_path)
    events = [
        {
            "claude_session_id": "sess-1",
            "transcript_offset": 100,
            "model": "claude-sonnet-4-6",
            "input_tokens": 1000,
            "output_tokens": 2000,
            "cache_creation_tokens": 0,
            "cache_read_tokens": 0,
        }
    ]
    res = await client.post(
        f"/internal/projects/{pid}/costs",
        json={"agent": "lead", "events": events},
        headers=HEADERS,
    )
    assert res.json()["inserted"] == 1
    # same offset again → deduped
    res = await client.post(
        f"/internal/projects/{pid}/costs",
        json={"agent": "lead", "events": events},
        headers=HEADERS,
    )
    assert res.json()["inserted"] == 0

    res = await client.get(f"/api/projects/{pid}/costs")
    summary = res.json()
    # 1000 in @ $3/M + 2000 out @ $15/M = 0.003 + 0.03
    assert abs(summary["total_usd"] - 0.033) < 1e-6
    assert summary["by_agent"][0]["agent"] == "lead"
    assert summary["total_tokens"] == 3000


async def test_mcp_approval_renders_config(client, tmp_path):
    pid = await _make_project(client, tmp_path)
    res = await client.post(
        f"/internal/projects/{pid}/mcp-suggestions",
        json={
            "agent": "lead",
            "suggestions": [
                {"name": "github", "reason": "PRs"},
                {"name": "not-in-catalog", "reason": "x"},
            ],
        },
        headers=HEADERS,
    )
    body = res.json()
    assert body["accepted"] == ["github"] and body["unknown"] == ["not-in-catalog"]

    res = await client.get(f"/api/projects/{pid}/mcp-suggestions")
    suggestion = res.json()[0]
    assert suggestion["status"] == "proposed"
    assert suggestion["env_keys"] == ["GITHUB_PERSONAL_ACCESS_TOKEN"]

    # approve without required env → 422
    res = await client.post(
        f"/api/mcp-suggestions/{suggestion['id']}/approve", json={"env_values": {}}
    )
    assert res.status_code == 422

    res = await client.post(
        f"/api/mcp-suggestions/{suggestion['id']}/approve",
        json={"env_values": {"GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_secret"}},
    )
    assert res.json()["status"] == "installed"

    # .mcp.json re-rendered with ${KEY} reference, no secret in file
    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        mcp_path = f"{project.host_dir}/repo/.mcp.json"
    config = json.loads(open(mcp_path).read())
    assert "github" in config["mcpServers"]
    assert (
        config["mcpServers"]["github"]["env"]["GITHUB_PERSONAL_ACCESS_TOKEN"]
        == "${GITHUB_PERSONAL_ACCESS_TOKEN}"
    )
    assert "ghp_secret" not in open(mcp_path).read()

    # secret travels via the internal desired-agents channel
    res = await client.get(f"/internal/projects/{pid}/agents", headers=HEADERS)
    assert res.json()["extra_env"]["GITHUB_PERSONAL_ACCESS_TOKEN"] == "ghp_secret"


async def test_wiki_api(client, tmp_path):
    pid = await _make_project(client, tmp_path)
    res = await client.get(f"/api/projects/{pid}/wiki/tree")
    names = {n["name"] for n in res.json()["tree"]}
    assert {"index.md", "log.md", "conventions.md", "pages"} <= names

    res = await client.get(f"/api/projects/{pid}/wiki/page", params={"path": "index.md"})
    assert "Wiki index" in res.json()["content"]

    res = await client.get(
        f"/api/projects/{pid}/wiki/page", params={"path": "../../PRD.md"}
    )
    assert res.status_code == 404


async def test_broadcast_delivered_to_every_agent(client, tmp_path):
    res = await client.post("/api/projects", json={"name": "Bcast", "prd_md": "# P"})
    pid = res.json()["id"]
    from tremblecode_server.models import AgentState, ProjectAgent

    async with SessionLocal() as session:
        for name in ("lead", "be-1"):
            session.add(
                ProjectAgent(
                    project_id=pid, name=name, role_key="x", state=AgentState.IDLE
                )
            )
        await session.commit()

    await client.post(
        f"/internal/projects/{pid}/messages",
        json={"from_agent": "lead", "to": "broadcast", "body_md": "standup"},
        headers=HEADERS,
    )
    for agent in ("lead", "be-1"):
        res = await client.get(
            f"/internal/projects/{pid}/messages/pending",
            params={"agent": agent},
            headers=HEADERS,
        )
        bodies = [m["body"] for m in res.json()["messages"]]
        assert "standup" in bodies, f"{agent} missed the broadcast"
    # second pull returns nothing (exactly-once per agent)
    res = await client.get(
        f"/internal/projects/{pid}/messages/pending",
        params={"agent": "be-1"},
        headers=HEADERS,
    )
    assert res.json()["messages"] == []
