"""shortcut key unique per user instead of globally

Revision ID: c3f1b2a9d8e7
Revises: 4d3c69f6cc61
Create Date: 2026-03-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c3f1b2a9d8e7'
down_revision: Union[str, Sequence[str], None] = '4d3c69f6cc61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the global unique index on key
    op.drop_index('ix_shortcut_messages_key', table_name='shortcut_messages')
    # Create a non-unique index on key (for search performance)
    op.create_index('ix_shortcut_messages_key', 'shortcut_messages', ['key'], unique=False)
    # Add composite unique constraint: key + created_by (unique per user)
    op.create_unique_constraint('uq_shortcut_key_per_user', 'shortcut_messages', ['key', 'created_by'])


def downgrade() -> None:
    op.drop_constraint('uq_shortcut_key_per_user', 'shortcut_messages', type_='unique')
    op.drop_index('ix_shortcut_messages_key', table_name='shortcut_messages')
    op.create_index('ix_shortcut_messages_key', 'shortcut_messages', ['key'], unique=True)
