"""feat: add tags to alertcatalog

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-09-25 09:15:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alertcatalog",
        sa.Column("tags", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alertcatalog", "tags")
