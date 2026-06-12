"""End-to-end workflow test through the HTTP API (no docker, no redis assertions
— bus publishes are fire-and-forget and tolerated to fail in tests)."""

import pytest

from tremblecode_server.config import get_settings
from tremblecode_server.database import SessionLocal
from tremblecode_server.models import Project

HEADERS = {"X-Tremblecode-Secret": get_settings().internal_secret}

PLAN = {
    "specs_md": "# Specs\nA CLI todo app.",
    "risks_md": "None.",
    "user_stories": [
        {
            "story_key": "US-001",
            "role": "user",
            "action": "add a todo",
            "benefit": "remember things",
            "acceptance_md": "todo add <text> persists",
        }
    ],
    "milestones": [
        {"key": "M1", "name": "Core CLI", "description": "add/list/done"},
    ],
    "tasks": [
        {
            "task_key": "T-001",
            "title": "Storage layer",
            "description_md": "JSON file storage",
            "role_key": "backend_dev",
            "milestone_key": "M1",
            "dependencies": [],
            "estimate_h": 2,
        },
        {
            "task_key": "T-002",
            "title": "CLI commands",
            "description_md": "add/list/done commands",
            "role_key": "backend_dev",
            "milestone_key": "M1",
            "dependencies": ["T-001"],
            "estimate_h": 3,
        },
    ],
    "mcp_suggestions": [{"name": "playwright", "reason": "UI tests later"}],
}


@pytest.fixture
async def workflow_project(client, tmp_path):
    res = await client.post(
        "/api/projects", json={"name": "Flow", "prd_md": "# PRD\ntodo app"}
    )
    pid = res.json()["id"]
    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        project.host_dir = str(tmp_path / "flow")
        project.port_base = 34100
        await session.commit()

    # provision skeleton + lead + workers manually (no docker in tests)
    from tremblecode_server.models import AgentState, ProjectAgent
    from tremblecode_server.services import provisioner

    async with SessionLocal() as session:
        project = await session.get(Project, pid)
        specs = await provisioner.roster_for_project(session, project)
        await provisioner.provision_project_skeleton(project, specs)
        for spec in specs:
            agent = ProjectAgent(
                project_id=pid,
                name=spec["name"],
                role_key=spec["role_key"],
                kind=spec["kind"],
                model=spec["model"],
                effort=spec["effort"],
                state=AgentState.IDLE,
                tmux_session=f"tc-{spec['name']}",
            )
            workspace = await provisioner.provision_agent_workspace(project, agent, spec)
            agent.workspace_path = str(workspace)
            session.add(agent)
        await session.commit()
    return pid


async def test_full_workflow(client, workflow_project):
    pid = workflow_project

    # internal endpoints reject without secret
    res = await client.post(f"/internal/projects/{pid}/plan/submit", json={})
    assert res.status_code == 403

    # invalid plan → validation errors
    bad = {**PLAN, "tasks": [{**PLAN["tasks"][0], "role_key": "nonexistent"}]}
    res = await client.post(
        f"/internal/projects/{pid}/plan/submit",
        json={"agent": "lead", "plan": bad},
        headers=HEADERS,
    )
    assert res.json()["ok"] is False
    assert any("nonexistent" in e for e in res.json()["validation_errors"])

    # only lead can submit
    res = await client.post(
        f"/internal/projects/{pid}/plan/submit",
        json={"agent": "be-1", "plan": PLAN},
        headers=HEADERS,
    )
    assert res.status_code == 403

    # valid submit
    res = await client.post(
        f"/internal/projects/{pid}/plan/submit",
        json={"agent": "lead", "plan": PLAN},
        headers=HEADERS,
    )
    assert res.json()["ok"] is True

    res = await client.get(f"/api/projects/{pid}")
    assert res.json()["status"] == "PLAN_REVIEW"

    # plan visible + editable
    res = await client.get(f"/api/projects/{pid}/plan")
    plan = res.json()
    assert len(plan["tasks"]) == 2 and len(plan["milestones"]) == 1
    task_ids = {t["task_key"]: t["id"] for t in plan["tasks"]}
    res = await client.patch(
        f"/api/tasks/{task_ids['T-001']}", json={"estimate_h": 4.0}
    )
    assert res.json()["estimate_h"] == 4.0

    # mcp suggestion captured from plan
    res = await client.get(f"/api/projects/{pid}/escalations")
    assert res.status_code == 200

    # approve → EXECUTING + first milestone active
    res = await client.post(f"/api/plans/{plan['id']}/approve")
    assert res.status_code == 200
    res = await client.get(f"/api/projects/{pid}")
    assert res.json()["status"] == "EXECUTING"
    res = await client.get(f"/api/projects/{pid}/plan")
    assert res.json()["milestones"][0]["status"] == "active"
    milestone_id = res.json()["milestones"][0]["id"]

    # T-002 claim must fail (dependency), T-001 claim works; double-claim fails
    res = await client.post(
        f"/internal/projects/{pid}/tasks/claim",
        json={"agent": "be-1", "task_id": "T-002"},
        headers=HEADERS,
    )
    assert res.status_code == 409
    res = await client.post(
        f"/internal/projects/{pid}/tasks/claim",
        json={"agent": "be-1", "task_id": "T-001"},
        headers=HEADERS,
    )
    assert res.json()["ok"] is True
    res = await client.post(
        f"/internal/projects/{pid}/tasks/claim",
        json={"agent": "be-1", "task_id": "T-001"},
        headers=HEADERS,
    )
    assert res.status_code == 409

    # qa can't claim dev task
    # start → branch created
    res = await client.post(
        f"/internal/projects/{pid}/tasks/start",
        json={"agent": "be-1", "task_id": "T-001"},
        headers=HEADERS,
    )
    body = res.json()
    assert body["branch"].startswith("task/t-001")

    # request review → routed to qa-1
    res = await client.post(
        f"/internal/projects/{pid}/tasks/request-review",
        json={"agent": "be-1", "task_id": "T-001", "notes": "run pytest"},
        headers=HEADERS,
    )
    assert res.json()["reviewer"] == "qa-1"

    # only the routed QA can review; dev cannot
    res = await client.post(
        f"/internal/projects/{pid}/tasks/review",
        json={"agent": "be-1", "task_id": "T-001", "verdict": "approve", "notes": ""},
        headers=HEADERS,
    )
    assert res.status_code == 403

    # request changes → back to dev
    res = await client.post(
        f"/internal/projects/{pid}/tasks/review",
        json={
            "agent": "qa-1",
            "task_id": "T-001",
            "verdict": "request_changes",
            "notes": "1. tests missing",
        },
        headers=HEADERS,
    )
    assert res.json()["verdict"] == "request_changes"

    # dev re-requests review, QA approves → MERGING promoted (serialized queue)
    await client.post(
        f"/internal/projects/{pid}/tasks/request-review",
        json={"agent": "be-1", "task_id": "T-001", "notes": "fixed"},
        headers=HEADERS,
    )
    res = await client.post(
        f"/internal/projects/{pid}/tasks/review",
        json={"agent": "qa-1", "task_id": "T-001", "verdict": "approve", "notes": "ok"},
        headers=HEADERS,
    )
    res = await client.get(f"/internal/projects/{pid}/tasks", headers=HEADERS)
    statuses = {t["task_key"]: t["status"] for t in res.json()["tasks"]}
    assert statuses["T-001"] == "MERGING"

    # complete (lead only) → DONE; T-002 now unblocked
    res = await client.post(
        f"/internal/projects/{pid}/tasks/complete",
        json={"agent": "qa-1", "task_id": "T-001", "summary": "x"},
        headers=HEADERS,
    )
    assert res.status_code == 403
    res = await client.post(
        f"/internal/projects/{pid}/tasks/complete",
        json={"agent": "lead", "task_id": "T-001", "summary": "merged"},
        headers=HEADERS,
    )
    assert "T-002" in res.json()["ready_tasks"]

    # milestone gate blocked until all tasks done
    res = await client.post(
        f"/internal/projects/{pid}/milestones/complete",
        json={"agent": "lead", "milestone_id": milestone_id, "summary": "demo"},
        headers=HEADERS,
    )
    assert res.status_code == 409

    # finish T-002 quickly
    for action, payload in [
        ("assign", {"agent": "lead", "task_id": "T-002", "assignee": "be-1"}),
        ("start", {"agent": "be-1", "task_id": "T-002"}),
        ("request-review", {"agent": "be-1", "task_id": "T-002", "notes": "n"}),
        ("review", {"agent": "qa-1", "task_id": "T-002", "verdict": "approve", "notes": ""}),
        ("complete", {"agent": "lead", "task_id": "T-002", "summary": "s"}),
    ]:
        res = await client.post(
            f"/internal/projects/{pid}/tasks/{action}", json=payload, headers=HEADERS
        )
        assert res.status_code == 200, f"{action}: {res.text}"

    # gate opens → escalation in inbox → approve → project COMPLETED
    res = await client.post(
        f"/internal/projects/{pid}/milestones/complete",
        json={"agent": "lead", "milestone_id": milestone_id, "summary": "demo ready"},
        headers=HEADERS,
    )
    escalation_id = res.json()["escalation_id"]
    res = await client.get("/api/inbox")
    assert any(e["id"] == escalation_id for e in res.json())
    res = await client.post(
        f"/api/escalations/{escalation_id}/respond",
        json={"option": "approve", "response": "nice work"},
    )
    assert res.json()["status"] == "answered"
    res = await client.get(f"/api/projects/{pid}")
    assert res.json()["status"] == "COMPLETED"


async def _submit_and_approve_plan(client, pid: str) -> None:
    res = await client.post(
        f"/internal/projects/{pid}/plan/submit",
        json={"agent": "lead", "plan": PLAN},
        headers=HEADERS,
    )
    assert res.json()["ok"] is True
    res = await client.get(f"/api/projects/{pid}/plan")
    res = await client.post(f"/api/plans/{res.json()['id']}/approve")
    assert res.status_code == 200


async def test_effort_seeded_and_flows(client, workflow_project):
    pid = workflow_project
    res = await client.get(f"/internal/projects/{pid}/agents", headers=HEADERS)
    efforts = {a["name"]: a["effort"] for a in res.json()["agents"]}
    assert efforts["lead"] == "high"
    assert efforts["be-1"] == "medium"
    assert efforts["qa-1"] == "medium"


async def test_plan_approval_sets_lead_effort_medium(client, workflow_project):
    pid = workflow_project
    await _submit_and_approve_plan(client, pid)
    res = await client.get(f"/internal/projects/{pid}/agents", headers=HEADERS)
    efforts = {a["name"]: a["effort"] for a in res.json()["agents"]}
    assert efforts["lead"] == "medium"


async def test_assign_message_is_pointer(client, workflow_project):
    pid = workflow_project
    await _submit_and_approve_plan(client, pid)
    res = await client.post(
        f"/internal/projects/{pid}/tasks/assign",
        json={"agent": "lead", "task_id": "T-001", "assignee": "be-1"},
        headers=HEADERS,
    )
    assert res.json()["ok"] is True
    res = await client.get(
        f"/internal/projects/{pid}/messages/pending",
        params={"agent": "be-1"},
        headers=HEADERS,
    )
    brief = next(
        m for m in res.json()["messages"] if m["subject"].startswith("Task assigned")
    )
    assert "T-001" in brief["body"] and "start_task" in brief["body"]
    # the full task description must NOT be duplicated into the message —
    # it rides the standing context instead
    assert "JSON file storage" not in brief["body"]


async def test_context_includes_assigned_brief_and_wiki(client, workflow_project, tmp_path):
    pid = workflow_project
    await _submit_and_approve_plan(client, pid)
    await client.post(
        f"/internal/projects/{pid}/tasks/assign",
        json={"agent": "lead", "task_id": "T-001", "assignee": "be-1"},
        headers=HEADERS,
    )
    index = tmp_path / "flow" / "repo" / ".wiki" / "index.md"
    index.write_text(index.read_text() + "\nWIKI-MARKER-LINE\n")

    res = await client.get(
        f"/internal/projects/{pid}/agents/be-1/context", headers=HEADERS
    )
    ctx = res.json()["context"]
    # assigned (not yet started) task brief is present
    assert "T-001" in ctx and "JSON file storage" in ctx and "ASSIGNED" in ctx
    # wiki index content is inlined, not just pointed at
    assert "WIKI-MARKER-LINE" in ctx
    assert ".wiki/onboarding/backend_dev.md" in ctx

    # oversized index gets truncated
    index.write_text("x" * 5000)
    res = await client.get(
        f"/internal/projects/{pid}/agents/be-1/context", headers=HEADERS
    )
    assert "truncated" in res.json()["context"]


async def test_review_request_message_has_no_brief(client, workflow_project):
    pid = workflow_project
    await _submit_and_approve_plan(client, pid)
    for action, payload in [
        ("claim", {"agent": "be-1", "task_id": "T-001"}),
        ("start", {"agent": "be-1", "task_id": "T-001"}),
        ("request-review", {"agent": "be-1", "task_id": "T-001", "notes": "check the storage round-trip"}),
    ]:
        res = await client.post(
            f"/internal/projects/{pid}/tasks/{action}", json=payload, headers=HEADERS
        )
        assert res.status_code == 200, f"{action}: {res.text}"
    res = await client.get(
        f"/internal/projects/{pid}/messages/pending",
        params={"agent": "qa-1"},
        headers=HEADERS,
    )
    review = next(
        m for m in res.json()["messages"] if m["subject"].startswith("Review requested")
    )
    assert "task/t-001" in review["body"] and "check the storage round-trip" in review["body"]
    assert "list_tasks" in review["body"]
    assert "JSON file storage" not in review["body"]


async def test_request_review_warns_without_wiki_changes(client, workflow_project, tmp_path):
    from tremblecode_server.services import git_service

    pid = workflow_project
    await _submit_and_approve_plan(client, pid)
    for action, payload in [
        ("claim", {"agent": "be-1", "task_id": "T-001"}),
        ("start", {"agent": "be-1", "task_id": "T-001"}),
    ]:
        await client.post(
            f"/internal/projects/{pid}/tasks/{action}", json=payload, headers=HEADERS
        )
    res = await client.post(
        f"/internal/projects/{pid}/tasks/request-review",
        json={"agent": "be-1", "task_id": "T-001", "notes": "n"},
        headers=HEADERS,
    )
    assert ".wiki" in res.json().get("warning", "")
    branch = next(
        t["branch"]
        for t in (await client.get(f"/internal/projects/{pid}/tasks", headers=HEADERS)).json()["tasks"]
        if t["task_key"] == "T-001"
    )

    # bounce back to the dev, commit a wiki change on the branch, re-request
    await client.post(
        f"/internal/projects/{pid}/tasks/review",
        json={"agent": "qa-1", "task_id": "T-001", "verdict": "request_changes", "notes": "1. x"},
        headers=HEADERS,
    )
    repo = tmp_path / "flow" / "repo"
    await git_service.run_git(["checkout", branch], repo)
    log = repo / ".wiki" / "log.md"
    log.write_text(log.read_text() + "\n## [2026-06-12] be-1 — T-001 ingest\n")
    await git_service.run_git(["add", ".wiki/log.md"], repo)
    await git_service.run_git(["commit", "-m", "wiki: T-001 ingest"], repo)
    await git_service.run_git(["checkout", "main"], repo)

    res = await client.post(
        f"/internal/projects/{pid}/tasks/request-review",
        json={"agent": "be-1", "task_id": "T-001", "notes": "fixed"},
        headers=HEADERS,
    )
    assert res.status_code == 200
    assert "warning" not in res.json()


async def test_agent_escalation_and_messages(client, workflow_project):
    pid = workflow_project
    res = await client.post(
        f"/internal/projects/{pid}/escalations",
        json={
            "agent": "be-1",
            "topic": "Delete prod data?",
            "body_md": "Migration requires dropping a table.",
            "type": "destructive_op",
            "blocking": True,
        },
        headers=HEADERS,
    )
    eid = res.json()["escalation_id"]
    res = await client.post(
        f"/api/escalations/{eid}/respond", json={"response": "No — rename it instead."}
    )
    assert res.status_code == 200
    # the answer landed as a message for the agent
    res = await client.get(
        f"/internal/projects/{pid}/messages/pending",
        params={"agent": "be-1"},
        headers=HEADERS,
    )
    bodies = [m["body"] for m in res.json()["messages"]]
    assert any("rename it instead" in b for b in bodies)

    # ack flow
    res = await client.post(
        f"/internal/projects/{pid}/messages",
        json={
            "from_agent": "be-1",
            "to": "lead",
            "body_md": "Need the API contract for T-002",
            "ack_requested": True,
        },
        headers=HEADERS,
    )
    msg_id = res.json()["message_id"]
    res = await client.post(
        f"/internal/messages/{msg_id}/ack",
        json={"agent": "lead", "note": "on it"},
        headers=HEADERS,
    )
    assert res.json()["ok"] is True
    res = await client.get(f"/api/projects/{pid}/messages")
    msg = next(m for m in res.json() if m["id"] == msg_id)
    assert msg["status"] == "acked" and msg["ack_note"] == "on it"
