"""add_oauth_token_columns_to_users

Revision ID: 7a1b2c3d4e5f
Revises: 636b45168c11
Create Date: 2026-10-03

Step 7: store encrypted GitHub OAuth tokens on users for private repo analytics.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7a1b2c3d4e5f"
down_revision: Union[str, Sequence[str], None] = "636b45168c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("github_token_encrypted", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("token_scope", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("token_obtained_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("token_obtained_at")
        batch_op.drop_column("token_scope")
        batch_op.drop_column("github_token_encrypted")
