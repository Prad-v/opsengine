"""feat: add temporalworkflowcatalog for Keep-managed Temporal registry

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
Create Date: 2026-09-10 12:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "temporalworkflowcatalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("catalog_key", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=2048), nullable=True),
        sa.Column("workflow_type", sa.String(length=255), nullable=False),
        sa.Column("task_queue", sa.String(length=255), nullable=False),
        sa.Column("workflow_id_template", sa.String(length=1024), nullable=True),
        sa.Column("input_mapping", sa.JSON(), nullable=True),
        sa.Column("provider_id", sa.String(length=255), nullable=False),
        sa.Column("disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "catalog_key",
            name="uq_temporalworkflowcatalog_tenant_key",
        ),
    )
    op.create_index(
        "ix_temporalworkflowcatalog_tenant_id",
        "temporalworkflowcatalog",
        ["tenant_id"],
    )
    op.create_index(
        "ix_temporalworkflowcatalog_provider_id",
        "temporalworkflowcatalog",
        ["provider_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_temporalworkflowcatalog_provider_id",
        table_name="temporalworkflowcatalog",
    )
    op.drop_index(
        "ix_temporalworkflowcatalog_tenant_id",
        table_name="temporalworkflowcatalog",
    )
    op.drop_table("temporalworkflowcatalog")
