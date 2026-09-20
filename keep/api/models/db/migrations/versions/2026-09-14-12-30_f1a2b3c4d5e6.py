"""feat: add approval policies and requests

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-09-14 12:30:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e0f1a2b3c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "approvalpolicy",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("cel", sa.String(length=4096), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approver_roles", sa.JSON(), nullable=True),
        sa.Column("approver_emails", sa.JSON(), nullable=True),
        sa.Column("allow_self_approve", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("min_approvals", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(length=255), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvalpolicy_tenant_id", "approvalpolicy", ["tenant_id"])
    op.create_index(
        "ix_approvalpolicy_tenant_action",
        "approvalpolicy",
        ["tenant_id", "action_type"],
    )

    op.create_table(
        "approvalrequest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=False),
        sa.Column("policy_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("summary", sa.String(length=2048), nullable=True),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=True),
        sa.Column("context_json", sa.JSON(), nullable=True),
        sa.Column("callback_json", sa.JSON(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=512), nullable=True),
        sa.Column("requested_by", sa.String(length=255), nullable=False),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("decided_by", sa.String(length=255), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_comment", sa.String(length=2048), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["approvalpolicy.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvalrequest_tenant_id", "approvalrequest", ["tenant_id"])
    op.create_index(
        "ix_approvalrequest_tenant_status",
        "approvalrequest",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_approvalrequest_tenant_idempotency",
        "approvalrequest",
        ["tenant_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_approvalrequest_tenant_idempotency", table_name="approvalrequest")
    op.drop_index("ix_approvalrequest_tenant_status", table_name="approvalrequest")
    op.drop_index("ix_approvalrequest_tenant_id", table_name="approvalrequest")
    op.drop_table("approvalrequest")
    op.drop_index("ix_approvalpolicy_tenant_action", table_name="approvalpolicy")
    op.drop_index("ix_approvalpolicy_tenant_id", table_name="approvalpolicy")
    op.drop_table("approvalpolicy")
