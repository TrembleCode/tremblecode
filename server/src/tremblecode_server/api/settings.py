from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from ..models import Setting
from ..services.secrets import encrypt
from ..services.settings_store import DEFAULT_SETTINGS, put_setting
from .deps import SessionDep

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsUpdate(BaseModel):
    values: dict[str, dict]


@router.get("")
async def read_settings(session: SessionDep):
    rows = await session.scalars(select(Setting))
    stored = {row.key: row.value for row in rows}
    merged = {**DEFAULT_SETTINGS, **stored}
    # never expose the encrypted key material
    if merged.get("auth", {}).get("anthropic_api_key_encrypted"):
        merged["auth"] = {**merged["auth"], "anthropic_api_key_encrypted": "***"}
    return merged


@router.put("")
async def write_settings(payload: SettingsUpdate, session: SessionDep):
    for key, value in payload.values.items():
        if key == "auth" and value.get("anthropic_api_key"):
            value = {
                "mode": value.get("mode", "api_key"),
                "anthropic_api_key_encrypted": encrypt(value.pop("anthropic_api_key")),
            }
        await put_setting(session, key, value)
    await session.commit()
    return {"ok": True}
