"""feat: add domain and role to alertcatalog

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-10-08 09:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alertcatalog",
        sa.Column("domain", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "alertcatalog",
        sa.Column("role", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alertcatalog", "role")
    op.drop_column("alertcatalog", "domain")
