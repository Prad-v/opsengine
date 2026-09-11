"""feat: add syntheticcheck for Temporal-backed blackbox probes

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-09-11 09:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c8d9e0f1a2b3"
down_revision = "b7c8d9e0f1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "syntheticcheck",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("check_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=True),
        sa.Column("prober", sa.String(length=32), nullable=False),
        sa.Column("module_config", sa.JSON(), nullable=True),
        sa.Column("targets", sa.JSON(), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("labels", sa.JSON(), nullable=True),
        sa.Column("task_queue", sa.String(length=255), nullable=False, server_default="keep-synth"),
        sa.Column("temporal_provider_id", sa.String(length=255), nullable=False),
        sa.Column("schedule_id", sa.String(length=255), nullable=True),
        sa.Column("last_results", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "check_key",
            name="uq_syntheticcheck_tenant_key",
        ),
    )
    op.create_index(
        "ix_syntheticcheck_tenant_id",
        "syntheticcheck",
        ["tenant_id"],
    )
    op.create_index(
        "ix_syntheticcheck_temporal_provider_id",
        "syntheticcheck",
        ["temporal_provider_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_syntheticcheck_temporal_provider_id",
        table_name="syntheticcheck",
    )
    op.drop_index(
        "ix_syntheticcheck_tenant_id",
        table_name="syntheticcheck",
    )
    op.drop_table("syntheticcheck")
