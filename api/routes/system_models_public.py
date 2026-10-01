"""
api/routes/system_models_public.py

Public (authenticated) endpoint that returns the active Dailsmart-managed
model catalogue. Used by the UI workflow builder to populate model dropdowns
alongside BYOK options.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from api.db import db_client
from api.db.models import SystemAIModelModel, UserModel
from api.services.auth.depends import get_user

router = APIRouter(prefix="/system-models", tags=["system-models"])


class PublicModelResponse(BaseModel):
    id: int
    provider: str
    service_type: str
    model_name: str
    display_name: str
    api_base_url: Optional[str]

    model_config = {"from_attributes": True}


@router.get("", response_model=List[PublicModelResponse])
async def list_active_system_models(
    service_type: Optional[str] = None,
    _user: UserModel = Depends(get_user),
):
    """Return all active Dailsmart-managed models for the given service_type.

    These are shown alongside BYOK options in the workflow builder so users
    can pick a Dailsmart-provided model without entering their own API key.
    """
    async with db_client.get_async_session() as session:
        stmt = (
            select(SystemAIModelModel)
            .where(SystemAIModelModel.is_active.is_(True))
        )
        if service_type:
            stmt = stmt.where(SystemAIModelModel.service_type == service_type)
        stmt = stmt.order_by(SystemAIModelModel.provider, SystemAIModelModel.display_name)
        result = await session.execute(stmt)
        return result.scalars().all()
