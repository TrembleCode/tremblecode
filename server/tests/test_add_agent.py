from pathlib import Path

from tremblecode_server.config import get_settings
from tremblecode_server.database import SessionLocal
from tremblecode_server.models import Project

HEADERS = {"X-Tremblecode-Secret": get_settings().internal_secret}


async def _project_with_lead(client, tmp_path):
    res = await client.post("/api/projects", json={"name": "Grow", "prd_md": "# P"})
    pid = res.json()["id"]
    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        project.host_dir = str(tmp_path / "grow")
        project.port_base = 34300
        await session.commit()

    from tremblecode_server.models import AgentState, ProjectAgent
    from tremblecode_server.services import provisioner

    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        specs = await provisioner.roster_for_project(session, project)
        await provisioner.provision_project_skeleton(project, specs)
        lead_spec = next(s for s in specs if s["kind"] == "lead")
        lead = ProjectAgent(
            project_id=pid,
            name="lead",
            role_key="team_lead",
            kind="lead",
            state=AgentState.IDLE,
        )
        lead.workspace_path = str(
            await provisioner.provision_agent_workspace(project, lead, lead_spec)
        )
        session.add(lead)
        await session.commit()
    return pid


async def test_add_agent_endpoint(client, tmp_path):
    pid = await _project_with_lead(client, tmp_path)

    res = await client.post(f"/api/projects/{pid}/agents", json={"role_key": "qa"})
    assert res.status_code == 201
    agent = res.json()
    assert agent["name"] == "qa-1" and agent["kind"] == "qa"

    # workspace + identity provisioned (relay will pick it up)
    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        host = Path(project.host_dir)
        roster = {
            e["role_key"]: e["count"] for e in project.config_json["roster"]
        }
    assert (host / "worktrees" / "qa-1" / ".claude" / "settings.json").exists()
    assert (host / ".tremblecode" / "agents" / "qa-1" / "identity.md").exists()
    assert roster["qa"] == 2  # default 1 + the added one

    # name allocation increments
    res = await client.post(f"/api/projects/{pid}/agents", json={"role_key": "qa"})
    assert res.json()["name"] == "qa-2"

    # no second lead
    res = await client.post(
        f"/api/projects/{pid}/agents", json={"role_key": "team_lead"}
    )
    assert res.status_code == 409
    # unknown role
    res = await client.post(f"/api/projects/{pid}/agents", json={"role_key": "nope"})
    assert res.status_code == 404


async def test_lead_requests_agents_with_approval(client, tmp_path):
    pid = await _project_with_lead(client, tmp_path)

    # only lead may request
    res = await client.post(
        f"/internal/projects/{pid}/agent-requests",
        json={"agent": "lead", "role_key": "backend_dev", "count": 2, "reason": "parallel work"},
        headers=HEADERS,
    )
    assert res.status_code == 200
    eid = res.json()["escalation_id"]

    res = await client.get("/api/inbox")
    escalation = next(e for e in res.json() if e["id"] == eid)
    assert escalation["type"] == "agent_request"
    assert "approve" in escalation["options"]

    # approve → agents spawn, lead gets a message
    res = await client.post(
        f"/api/escalations/{eid}/respond", json={"option": "approve"}
    )
    assert res.status_code == 200
    res = await client.get(f"/api/projects/{pid}/agents")
    names = {a["name"] for a in res.json()}
    assert {"be-1", "be-2"} <= names

    res = await client.get(
        f"/internal/projects/{pid}/messages/pending",
        params={"agent": "lead"},
        headers=HEADERS,
    )
    assert any("be-1" in m["body"] for m in res.json()["messages"])

    # rejection path
    res = await client.post(
        f"/internal/projects/{pid}/agent-requests",
        json={"agent": "lead", "role_key": "qa", "count": 1, "reason": "x"},
        headers=HEADERS,
    )
    eid2 = res.json()["escalation_id"]
    await client.post(
        f"/api/escalations/{eid2}/respond",
        json={"option": "reject", "response": "not needed yet"},
    )
    res = await client.get(f"/api/projects/{pid}/agents")
    assert not any(a["role_key"] == "qa" for a in res.json())
