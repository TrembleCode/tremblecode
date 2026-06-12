from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import AgentTemplate

BUILTIN_TEMPLATES = [
    {
        "role_key": "team_lead",
        "display_name": "Team Lead",
        "description": "Decomposes the PRD, assigns tasks, merges approved branches, gates milestones.",
        "model": "opus",
        "effort": "high",  # dropped to medium after plan approval
        "default_count": 1,
        "color": "#ff9900",
        "kind": "lead",
    },
    {
        "role_key": "backend_dev",
        "display_name": "Backend Developer",
        "description": "APIs, services, data models, migrations, background jobs.",
        "model": "sonnet",
        "effort": "medium",
        "default_count": 1,
        "color": "#33ff57",
        "kind": "dev",
    },
    {
        "role_key": "frontend_dev",
        "display_name": "Frontend Developer",
        "description": "Web/Flutter UIs, components, styling, client state.",
        "model": "sonnet",
        "effort": "medium",
        "default_count": 1,
        "color": "#00ccff",
        "kind": "dev",
    },
    {
        "role_key": "qa",
        "display_name": "QA Engineer",
        "description": "Reviews task branches, runs suites, verifies acceptance criteria.",
        "model": "sonnet",
        "effort": "medium",
        "default_count": 1,
        "color": "#ff2244",
        "kind": "qa",
    },
]


async def seed_builtin_templates(session: AsyncSession) -> None:
    count = await session.scalar(select(func.count()).select_from(AgentTemplate))
    if count:
        return
    roles_dir = get_settings().templates_dir / "roles"
    for spec in BUILTIN_TEMPLATES:
        prompt_file = roles_dir / f"{spec['role_key']}.md"
        prompt = prompt_file.read_text() if prompt_file.exists() else ""
        session.add(AgentTemplate(**spec, system_prompt_md=prompt, is_builtin=True))
    await session.commit()
