from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Setting

# Defaults; pricing is per MTok USD.
DEFAULT_SETTINGS: dict[str, dict] = {
    "auth": {"mode": "subscription", "anthropic_api_key_encrypted": None},
    "pricing": {
        "models": {
            "claude-opus-4-8": {"input": 5.0, "output": 25.0, "cache_write": 6.25, "cache_read": 0.5},
            "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
            "claude-haiku-4-5": {"input": 1.0, "output": 5.0, "cache_write": 1.25, "cache_read": 0.1},
        },
        "fallback": {"input": 3.0, "output": 15.0, "cache_write": 3.75, "cache_read": 0.3},
    },
    "defaults": {"lead_model": "opus", "worker_model": "sonnet"},
}


async def get_setting(session: AsyncSession, key: str) -> dict:
    row = await session.get(Setting, key)
    return row.value if row else DEFAULT_SETTINGS.get(key, {})


async def put_setting(session: AsyncSession, key: str, value: dict) -> None:
    row = await session.get(Setting, key)
    if row:
        row.value = value
    else:
        session.add(Setting(key=key, value=value))
