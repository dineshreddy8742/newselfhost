"""
api/routes/admin.py
Superadmin-only endpoints for:
  - Managing the system AI model catalogue (Dailsmart-managed models)
  - Managing organisation billing (grant credits, view ledger)
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, update

from api.db import db_client
from api.db.models import (
    OrgBillingAccountModel,
    OrgBillingLedgerModel,
    SystemAIModelModel,
    UserModel,
)
from api.services.auth.depends import get_superuser

router = APIRouter(prefix="/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

ServiceType = Literal["llm", "tts", "stt", "realtime", "embeddings"]


class SystemAIModelCreate(BaseModel):
    provider: str = Field(..., description="Provider key, e.g. 'openai', 'sarvam', 'custom'")
    service_type: ServiceType
    model_name: str = Field(..., description="Machine-readable model ID, e.g. 'gpt-4o'")
    display_name: str = Field(..., description="Human-readable label shown in UI")
    api_base_url: Optional[str] = None
    is_active: bool = True
    config_schema: dict = Field(default_factory=dict)
    extra_config: dict = Field(default_factory=dict)


class SystemAIModelUpdate(BaseModel):
    display_name: Optional[str] = None
    api_base_url: Optional[str] = None
    is_active: Optional[bool] = None
    config_schema: Optional[dict] = None
    extra_config: Optional[dict] = None


class SystemAIModelResponse(BaseModel):
    id: int
    provider: str
    service_type: str
    model_name: str
    display_name: str
    api_base_url: Optional[str]
    is_active: bool
    config_schema: dict
    extra_config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BillingGrantRequest(BaseModel):
    organization_id: int
    credits: float = Field(..., gt=0, description="Credits to add (in INR paisa equivalents)")
    description: str = "Admin credit grant"


class BillingLedgerEntryResponse(BaseModel):
    id: int
    organization_id: int
    entry_type: str
    credits_delta: float
    quantity: Optional[float]
    quantity_unit: Optional[str]
    rate: Optional[float]
    description: Optional[str]
    workflow_run_id: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class OrgBillingAccountResponse(BaseModel):
    organization_id: int
    credits_balance: float
    currency: str
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# System AI Model endpoints
# ---------------------------------------------------------------------------


@router.get("/models", response_model=List[SystemAIModelResponse])
async def list_system_models(
    service_type: Optional[ServiceType] = None,
    active_only: bool = False,
    _user: UserModel = Depends(get_superuser),
):
    """List all superadmin-managed AI models."""
    async with db_client.get_async_session() as session:
        stmt = select(SystemAIModelModel)
        if service_type:
            stmt = stmt.where(SystemAIModelModel.service_type == service_type)
        if active_only:
            stmt = stmt.where(SystemAIModelModel.is_active.is_(True))
        stmt = stmt.order_by(SystemAIModelModel.service_type, SystemAIModelModel.provider)
        result = await session.execute(stmt)
        return result.scalars().all()


@router.post("/models", response_model=SystemAIModelResponse, status_code=201)
async def create_system_model(
    body: SystemAIModelCreate,
    _user: UserModel = Depends(get_superuser),
):
    """Register a new AI model in the global catalogue."""
    async with db_client.get_async_session() as session:
        model = SystemAIModelModel(
            provider=body.provider,
            service_type=body.service_type,
            model_name=body.model_name,
            display_name=body.display_name,
            api_base_url=body.api_base_url,
            is_active=body.is_active,
            config_schema=body.config_schema,
            extra_config=body.extra_config,
        )
        session.add(model)
        await session.commit()
        await session.refresh(model)
        return model


@router.put("/models/{model_id}", response_model=SystemAIModelResponse)
async def update_system_model(
    model_id: int,
    body: SystemAIModelUpdate,
    _user: UserModel = Depends(get_superuser),
):
    """Update an existing AI model entry."""
    async with db_client.get_async_session() as session:
        result = await session.execute(
            select(SystemAIModelModel).where(SystemAIModelModel.id == model_id)
        )
        model = result.scalar_one_or_none()
        if model is None:
            raise HTTPException(status_code=404, detail="Model not found")
        if body.display_name is not None:
            model.display_name = body.display_name
        if body.api_base_url is not None:
            model.api_base_url = body.api_base_url
        if body.is_active is not None:
            model.is_active = body.is_active
        if body.config_schema is not None:
            model.config_schema = body.config_schema
        if body.extra_config is not None:
            model.extra_config = body.extra_config
        model.updated_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(model)
        return model


@router.delete("/models/{model_id}", status_code=204)
async def delete_system_model(
    model_id: int,
    _user: UserModel = Depends(get_superuser),
):
    """Permanently remove a model from the catalogue."""
    async with db_client.get_async_session() as session:
        result = await session.execute(
            delete(SystemAIModelModel).where(SystemAIModelModel.id == model_id)
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Model not found")
        await session.commit()


# ---------------------------------------------------------------------------
# Public endpoint consumed by UI model-configuration dropdowns
# (no superuser required – any authenticated user can read the active list)
# ---------------------------------------------------------------------------


@router.get("/models/public", response_model=List[SystemAIModelResponse])
async def list_public_system_models(_user: UserModel = Depends(get_superuser)):
    """Active-only listing for building BYOK / Dailsmart dropdowns."""
    async with db_client.get_async_session() as session:
        result = await session.execute(
            select(SystemAIModelModel)
            .where(SystemAIModelModel.is_active.is_(True))
            .order_by(SystemAIModelModel.service_type, SystemAIModelModel.provider)
        )
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Billing endpoints
# ---------------------------------------------------------------------------

PLATFORM_RATE_PER_MINUTE_INR = Decimal("0.89")  # Charged for BYOK calls
DAILSMART_AI_RATE_PER_MINUTE_INR = Decimal("2.50")  # Additional AI usage for Dailsmart-managed


@router.get("/billing/{organization_id}", response_model=OrgBillingAccountResponse)
async def get_org_billing(
    organization_id: int,
    _user: UserModel = Depends(get_superuser),
):
    """Get credit balance for an organisation."""
    async with db_client.get_async_session() as session:
        result = await session.execute(
            select(OrgBillingAccountModel).where(
                OrgBillingAccountModel.organization_id == organization_id
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            # Auto-create with zero balance
            account = OrgBillingAccountModel(
                organization_id=organization_id,
                credits_balance=Decimal("0"),
            )
            session.add(account)
            await session.commit()
            await session.refresh(account)
        return account


@router.post("/billing/grant", response_model=OrgBillingAccountResponse)
async def grant_credits(
    body: BillingGrantRequest,
    _user: UserModel = Depends(get_superuser),
):
    """Grant credits to an organisation (admin action)."""
    async with db_client.get_async_session() as session:
        result = await session.execute(
            select(OrgBillingAccountModel).where(
                OrgBillingAccountModel.organization_id == body.organization_id
            )
        )
        account = result.scalar_one_or_none()
        if account is None:
            account = OrgBillingAccountModel(
                organization_id=body.organization_id,
                credits_balance=Decimal("0"),
            )
            session.add(account)
            await session.flush()

        amount = Decimal(str(body.credits))
        account.credits_balance += amount
        account.updated_at = datetime.now(UTC)

        ledger = OrgBillingLedgerModel(
            organization_id=body.organization_id,
            entry_type="grant",
            credits_delta=amount,
            description=body.description,
        )
        session.add(ledger)
        await session.commit()
        await session.refresh(account)
        return account


@router.get("/billing/{organization_id}/ledger", response_model=List[BillingLedgerEntryResponse])
async def get_org_ledger(
    organization_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    _user: UserModel = Depends(get_superuser),
):
    """Paginated ledger entries for an organisation."""
    async with db_client.get_async_session() as session:
        offset = (page - 1) * limit
        result = await session.execute(
            select(OrgBillingLedgerModel)
            .where(OrgBillingLedgerModel.organization_id == organization_id)
            .order_by(OrgBillingLedgerModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
