import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import CostEvent, ProjectAgent
from .settings_store import get_setting

logger = logging.getLogger(__name__)


def price_for(pricing: dict, model: str) -> dict:
    models = pricing.get("models", {})
    if model in models:
        return models[model]
    # fuzzy match: "claude-sonnet-4-6-20250901" → "claude-sonnet-4-6"
    for known, rates in models.items():
        if model.startswith(known) or known.startswith(model):
            return rates
    # family match (opus/sonnet/haiku)
    for family in ("opus", "sonnet", "haiku"):
        if family in model:
            for known, rates in models.items():
                if family in known:
                    return rates
    return pricing.get("fallback", {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3})


def compute_cost(rates: dict, event: dict) -> float:
    return (
        event.get("input_tokens", 0) * rates.get("input", 0)
        + event.get("output_tokens", 0) * rates.get("output", 0)
        + event.get("cache_creation_tokens", 0) * rates.get("cache_write", 0)
        + event.get("cache_read_tokens", 0) * rates.get("cache_read", 0)
    ) / 1_000_000


async def ingest_events(
    session: AsyncSession, project_id: str, agent_name: str, events: list[dict]
) -> int:
    agent = await session.scalar(
        select(ProjectAgent).where(
            ProjectAgent.project_id == project_id, ProjectAgent.name == agent_name
        )
    )
    if agent is None:
        return 0
    pricing = await get_setting(session, "pricing")
    inserted = 0
    for event in events:
        rates = price_for(pricing, event.get("model", ""))
        cost_event = CostEvent(
            project_id=project_id,
            agent_id=agent.id,
            claude_session_id=event.get("claude_session_id", ""),
            transcript_offset=event.get("transcript_offset", 0),
            model=event.get("model", ""),
            input_tokens=event.get("input_tokens", 0),
            output_tokens=event.get("output_tokens", 0),
            cache_creation_tokens=event.get("cache_creation_tokens", 0),
            cache_read_tokens=event.get("cache_read_tokens", 0),
            cost_usd=compute_cost(rates, event),
        )
        session.add(cost_event)
        try:
            await session.commit()
            inserted += 1
        except IntegrityError:
            await session.rollback()  # duplicate (session_id, offset) — idempotent
    return inserted


async def project_summary(session: AsyncSession, project_id: str) -> dict:
    agents = {
        a.id: a.name
        for a in await session.scalars(
            select(ProjectAgent).where(ProjectAgent.project_id == project_id)
        )
    }
    totals = await session.execute(
        select(
            func.coalesce(func.sum(CostEvent.cost_usd), 0.0),
            func.coalesce(
                func.sum(CostEvent.input_tokens + CostEvent.output_tokens), 0
            ),
        ).where(CostEvent.project_id == project_id)
    )
    total_usd, total_tokens = totals.one()

    by_agent_rows = await session.execute(
        select(
            CostEvent.agent_id,
            func.sum(CostEvent.cost_usd),
            func.sum(CostEvent.input_tokens),
            func.sum(CostEvent.output_tokens),
            func.sum(CostEvent.cache_read_tokens),
            func.sum(CostEvent.cache_creation_tokens),
        )
        .where(CostEvent.project_id == project_id)
        .group_by(CostEvent.agent_id)
    )
    by_day_rows = await session.execute(
        select(
            func.date(CostEvent.created_at),
            func.sum(CostEvent.cost_usd),
        )
        .where(CostEvent.project_id == project_id)
        .group_by(func.date(CostEvent.created_at))
        .order_by(func.date(CostEvent.created_at))
    )
    by_model_rows = await session.execute(
        select(CostEvent.model, func.sum(CostEvent.cost_usd))
        .where(CostEvent.project_id == project_id)
        .group_by(CostEvent.model)
    )
    return {
        "total_usd": round(total_usd, 4),
        "total_tokens": int(total_tokens),
        "by_agent": [
            {
                "agent": agents.get(agent_id, "?"),
                "cost_usd": round(cost, 4),
                "input_tokens": int(input_tokens or 0),
                "output_tokens": int(output_tokens or 0),
                "cache_read_tokens": int(cache_read or 0),
                "cache_write_tokens": int(cache_write or 0),
            }
            for agent_id, cost, input_tokens, output_tokens, cache_read, cache_write in by_agent_rows
        ],
        "by_day": [
            {"day": str(day), "cost_usd": round(cost, 4)} for day, cost in by_day_rows
        ],
        "by_model": [
            {"model": model, "cost_usd": round(cost, 4)}
            for model, cost in by_model_rows
        ],
    }
