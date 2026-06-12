from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..database import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def require_internal_secret(
    x_tremblecode_secret: Annotated[str | None, Header()] = None,
) -> None:
    if x_tremblecode_secret != get_settings().internal_secret:
        raise HTTPException(status_code=403, detail="invalid internal secret")
