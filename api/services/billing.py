"""
api/services/billing.py

Central billing engine for Dailsmart.

Rates (INR) — billed per FULL MINUTE (ceiling):
  PLATFORM_RATE_PER_MINUTE = 0.89   (every call, regardless of mode)
  AI_USAGE_RATE_PER_MINUTE = 1.89   (Dailsmart-managed mode only)

Rounding rule:
  Billable minutes = ceil(duration_seconds / 60)
  Examples:
    1s  → 1 min
    60s → 1 min
    61s → 2 min
    90s → 2 min
   121s → 3 min

Call this after a WorkflowRun completes with call duration.
The function is idempotent – if ledger already contains an entry for the
same workflow_run_id it will not double-charge.
"""
from __future__ import annotations

import logging
import math
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db.models import OrgBillingAccountModel, OrgBillingLedgerModel

log = logging.getLogger(__name__)

# ── Rates ──────────────────────────────────────────────────────────────────────
PLATFORM_RATE_PER_MINUTE = Decimal("0.89")   # charged on every call (BYOK + Dailsmart)
AI_USAGE_RATE_PER_MINUTE = Decimal("1.89")   # charged only for Dailsmart-managed mode


def _billable_minutes(duration_seconds: float) -> int:
    """Convert raw seconds → billable minutes using ceiling.

    Any fraction of a minute beyond a full minute is rounded up to the
    next whole minute.

      0s  → 0 min   (no charge for 0-second calls)
      1s  → 1 min
     60s  → 1 min
     61s  → 2 min
    120s  → 2 min
    121s  → 3 min
    """
    if duration_seconds <= 0:
        return 0
    return math.ceil(duration_seconds / 60)


async def charge_call(
    session: AsyncSession,
    organization_id: int,
    workflow_run_id: int,
    duration_seconds: float,
    *,
    is_byok: bool = True,
) -> None:
    """Deduct call charges from an organisation's credit balance.

    Args:
        session:          Active async SQLAlchemy session.
        organization_id:  Organisation to charge.
        workflow_run_id:  Workflow run being charged.
        duration_seconds: Total call duration in seconds (raw).
        is_byok:          If True → only platform fee.
                          If False (Dailsmart-managed) → platform fee + AI usage fee.
    """
    # Guard against duplicate charging
    existing = await session.execute(
        select(OrgBillingLedgerModel).where(
            OrgBillingLedgerModel.workflow_run_id == workflow_run_id,
            OrgBillingLedgerModel.entry_type == "platform_usage",
        )
    )
    if existing.scalar_one_or_none() is not None:
        log.info("Billing: run %s already charged - skipping", workflow_run_id)
        return

    # Ceiling minute billing
    billable_mins = _billable_minutes(duration_seconds)
    billable_mins_dec = Decimal(str(billable_mins))

    entries: list[OrgBillingLedgerModel] = []

    # 1. Platform fee - always charged (BYOK and Dailsmart-managed)
    platform_charge = billable_mins_dec * PLATFORM_RATE_PER_MINUTE
    entries.append(
        OrgBillingLedgerModel(
            organization_id=organization_id,
            entry_type="platform_usage",
            credits_delta=-float(platform_charge),
            quantity=float(billable_mins),
            quantity_unit="minute",
            rate=float(PLATFORM_RATE_PER_MINUTE),
            description=(
                f"Platform fee: Rs.{PLATFORM_RATE_PER_MINUTE}/min x {billable_mins} min"
                f" (actual {duration_seconds:.1f}s)"
            ),
            workflow_run_id=workflow_run_id,
            meta={"is_byok": is_byok, "raw_seconds": duration_seconds},
        )
    )

    # 2. AI usage fee - only for Dailsmart-managed mode
    if not is_byok:
        ai_charge = billable_mins_dec * AI_USAGE_RATE_PER_MINUTE
        entries.append(
            OrgBillingLedgerModel(
                organization_id=organization_id,
                entry_type="ai_usage",
                credits_delta=-float(ai_charge),
                quantity=float(billable_mins),
                quantity_unit="minute",
                rate=float(AI_USAGE_RATE_PER_MINUTE),
                description=(
                    f"Dailsmart AI model: Rs.{AI_USAGE_RATE_PER_MINUTE}/min x {billable_mins} min"
                ),
                workflow_run_id=workflow_run_id,
                meta={"is_byok": False, "raw_seconds": duration_seconds},
            )
        )

    total_charge = sum(Decimal(str(-e.credits_delta)) for e in entries)

    # Upsert billing account
    result = await session.execute(
        select(OrgBillingAccountModel).where(
            OrgBillingAccountModel.organization_id == organization_id
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = OrgBillingAccountModel(
            organization_id=organization_id,
            credits_balance=0.0,
        )
        session.add(account)
        await session.flush()

    account.credits_balance = float(Decimal(str(account.credits_balance)) - total_charge)

    for entry in entries:
        session.add(entry)

    log.info(
        "Billing: org=%s run=%s raw=%.1fs billable=%dmin charged=Rs.%.4f byok=%s",
        organization_id,
        workflow_run_id,
        duration_seconds,
        billable_mins,
        total_charge,
        is_byok,
    )


async def get_balance(
    session: AsyncSession,
    organization_id: int,
) -> float:
    """Return current credit balance for an org (0.0 if no account yet)."""
    result = await session.execute(
        select(OrgBillingAccountModel).where(
            OrgBillingAccountModel.organization_id == organization_id
        )
    )
    account = result.scalar_one_or_none()
    return account.credits_balance if account else 0.0


async def has_sufficient_credits(
    session: AsyncSession,
    organization_id: int,
    min_credits: float = 0.89,
) -> bool:
    """Check if org has at least `min_credits` available."""
    balance = await get_balance(session, organization_id)
    return balance >= min_credits
