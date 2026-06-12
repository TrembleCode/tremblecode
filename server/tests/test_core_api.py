async def test_builtin_templates_seeded(client):
    res = await client.get("/api/agent-templates")
    assert res.status_code == 200
    roles = {t["role_key"] for t in res.json()}
    assert roles == {"team_lead", "backend_dev", "frontend_dev", "qa"}
    lead = next(t for t in res.json() if t["role_key"] == "team_lead")
    assert lead["kind"] == "lead"
    assert "Team Lead" in lead["system_prompt_md"]


async def test_template_crud(client):
    res = await client.post(
        "/api/agent-templates",
        json={
            "role_key": "mobile_dev",
            "display_name": "Mobile Developer",
            "system_prompt_md": "You build Flutter apps.",
            "kind": "dev",
        },
    )
    assert res.status_code == 201
    tpl_id = res.json()["id"]

    res = await client.patch(
        f"/api/agent-templates/{tpl_id}", json={"default_count": 2}
    )
    assert res.json()["default_count"] == 2

    res = await client.delete(f"/api/agent-templates/{tpl_id}")
    assert res.status_code == 204

    # builtins protected
    res = await client.get("/api/agent-templates")
    lead = next(t for t in res.json() if t["role_key"] == "team_lead")
    res = await client.delete(f"/api/agent-templates/{lead['id']}")
    assert res.status_code == 400


async def test_project_lifecycle(client):
    res = await client.post(
        "/api/projects", json={"name": "My App", "start_with_discussion": True}
    )
    assert res.status_code == 201
    body = res.json()
    assert body["slug"] == "my-app"
    assert body["status"] == "DISCUSSION"
    # default roster derived from templates
    assert {r["role_key"] for r in body["config_json"]["roster"]} == {
        "team_lead",
        "backend_dev",
        "frontend_dev",
        "qa",
    }
    pid = body["id"]

    # PRD upload moves DISCUSSION → DRAFT
    res = await client.put(f"/api/projects/{pid}/prd", json={"prd_md": "# PRD\nBuild it."})
    assert res.json()["status"] == "DRAFT"

    res = await client.get(f"/api/projects/{pid}")
    assert res.status_code == 200
    assert res.json()["prd_md"].startswith("# PRD")
    assert res.json()["agents"] == []

    # slug collision
    res = await client.post("/api/projects", json={"name": "My App", "prd_md": "x"})
    assert res.json()["slug"] == "my-app-2"
    assert res.json()["status"] == "DRAFT"

    res = await client.delete(f"/api/projects/{pid}")
    assert res.status_code == 204


async def test_pause_resume_revives_agents(client, monkeypatch, tmp_path):
    from tremblecode_server.database import SessionLocal
    from tremblecode_server.models import AgentState, Project, ProjectAgent, ProjectStatus
    from tremblecode_server.services import docker_service

    async def _noop(slug):
        return None

    async def _status(slug):
        return "exited"

    monkeypatch.setattr(docker_service, "stop_sandbox", _noop)
    monkeypatch.setattr(docker_service, "start_sandbox", _noop)
    monkeypatch.setattr(docker_service, "sandbox_status", _status)

    res = await client.post(
        "/api/projects", json={"name": "Pausable", "prd_md": "# PRD\nx"}
    )
    pid = res.json()["id"]
    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        project.status = ProjectStatus.EXECUTING
        project.container_id = "deadbeef"
        session.add(
            ProjectAgent(
                project_id=pid,
                name="lead",
                role_key="team_lead",
                kind="lead",
                model="sonnet",
                state=AgentState.IDLE,
                tmux_session="tc-lead",
                workspace_path=str(tmp_path / "lead-ws"),
            )
        )
        await session.commit()

    res = await client.post(f"/api/projects/{pid}/pause")
    assert res.json()["status"] == "PAUSED"
    res = await client.get(f"/api/projects/{pid}")
    assert res.json()["agents"][0]["state"] == "stopped"

    # resume must revive agents, otherwise the relay never relaunches tmux sessions
    res = await client.post(f"/api/projects/{pid}/resume")
    assert res.json()["status"] == "PLANNING"
    res = await client.get(f"/api/projects/{pid}")
    assert res.json()["agents"][0]["state"] == "starting"


async def test_settings_roundtrip(client):
    res = await client.get("/api/settings")
    assert res.status_code == 200
    assert res.json()["auth"]["mode"] == "subscription"

    res = await client.put(
        "/api/settings", json={"values": {"auth": {"mode": "api_key"}}}
    )
    assert res.status_code == 200
    res = await client.get("/api/settings")
    assert res.json()["auth"]["mode"] == "api_key"
