"""add media fields to messages

Revision ID: b2f8a3c1d4e5
Revises: 4d3c69f6cc61
Create Date: 2026-02-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2f8a3c1d4e5'
down_revision: Union[str, Sequence[str], None] = '4d3c69f6cc61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add media_url, media_type, media_filename columns to messages table."""
    op.add_column('messages', sa.Column('media_url', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('media_type', sa.String(), nullable=True))
    op.add_column('messages', sa.Column('media_filename', sa.String(), nullable=True))


def downgrade() -> None:
    """Remove media columns from messages table."""
    op.drop_column('messages', 'media_filename')
    op.drop_column('messages', 'media_type')
    op.drop_column('messages', 'media_url')
