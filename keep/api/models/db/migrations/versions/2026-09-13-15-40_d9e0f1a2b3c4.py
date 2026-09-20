"""feat: add alertcatalog for reserved alert codes

Revision ID: d9e0f1a2b3c4
Revises: c8d9e0f1a2b3
Create Date: 2026-09-13 15:40:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d9e0f1a2b3c4"
down_revision = "c8d9e0f1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alertcatalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=True),
        sa.Column("runbook_url", sa.String(length=2048), nullable=True),
        sa.Column("keep_workflow_id", sa.String(length=255), nullable=True),
        sa.Column("auto_run_on", sa.String(length=32), nullable=False, server_default="none"),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "code",
            name="uq_alertcatalog_tenant_code",
        ),
    )
    op.create_index(
        "ix_alertcatalog_tenant_id",
        "alertcatalog",
        ["tenant_id"],
    )
    op.create_index(
        "ix_alertcatalog_tenant_code",
        "alertcatalog",
        ["tenant_id", "code"],
    )


def downgrade() -> None:
    op.drop_index("ix_alertcatalog_tenant_code", table_name="alertcatalog")
    op.drop_index("ix_alertcatalog_tenant_id", table_name="alertcatalog")
    op.drop_table("alertcatalog")
