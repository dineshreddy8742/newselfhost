"""add_system_ai_models_and_billing_tables

Revision ID: a1f2b3c4d5e6
Revises: 9641b4f306cd
Create Date: 2026-09-30 11:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1f2b3c4d5e6"
down_revision: str | None = "9641b4f306cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. system_ai_models
    #    Superadmin-managed catalogue of available AI models / providers.
    #    These surface in the "Dailsmart" mode drop-downs and in
    #    /api/v1/admin/models endpoints.
    # ------------------------------------------------------------------
    op.create_table(
        "system_ai_models",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "service_type",
            sa.String(length=32),
            nullable=False,
            comment="llm | tts | stt | realtime | embeddings",
        ),
        sa.Column("model_name", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=False),
        sa.Column("api_base_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("config_schema", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("extra_config", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("provider", "service_type", "model_name", name="uq_system_ai_models"),
    )
    op.create_index("ix_system_ai_models_service_type", "system_ai_models", ["service_type"])
    op.create_index("ix_system_ai_models_is_active",   "system_ai_models", ["is_active"])

    # ------------------------------------------------------------------
    # 2. org_billing_accounts
    #    One row per organisation – tracks credit balance.
    # ------------------------------------------------------------------
    op.create_table(
        "org_billing_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("credits_balance", sa.Numeric(precision=18, scale=6), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_org_billing_accounts_org", "org_billing_accounts", ["organization_id"])

    # ------------------------------------------------------------------
    # 3. org_billing_ledger
    #    Append-only journal of every debit / credit.
    #    entry_type: 'grant' | 'topup' | 'platform_usage' | 'ai_usage'
    # ------------------------------------------------------------------
    op.create_table(
        "org_billing_ledger",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "organization_id",
            sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_type", sa.String(length=32), nullable=False),
        sa.Column("credits_delta", sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("quantity_unit", sa.String(length=32), nullable=True, comment="minute | call"),
        sa.Column("rate", sa.Numeric(precision=18, scale=6), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("workflow_run_id", sa.Integer(), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )
    op.create_index("ix_org_billing_ledger_org",     "org_billing_ledger", ["organization_id"])
    op.create_index("ix_org_billing_ledger_type",    "org_billing_ledger", ["entry_type"])
    op.create_index("ix_org_billing_ledger_created", "org_billing_ledger", ["created_at"])


def downgrade() -> None:
    op.drop_table("org_billing_ledger")
    op.drop_table("org_billing_accounts")
    op.drop_table("system_ai_models")
