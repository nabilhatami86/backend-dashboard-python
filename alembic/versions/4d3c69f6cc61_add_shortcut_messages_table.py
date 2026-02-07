"""add shortcut_messages table

Revision ID: 4d3c69f6cc61
Revises: 5ce1e4e66b2a
Create Date: 2026-02-07 08:30:56.954926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4d3c69f6cc61'
down_revision: Union[str, Sequence[str], None] = '5ce1e4e66b2a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('shortcut_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('values', sa.Text(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_shortcut_messages_id'), 'shortcut_messages', ['id'], unique=False)
    op.create_index(op.f('ix_shortcut_messages_key'), 'shortcut_messages', ['key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_shortcut_messages_key'), table_name='shortcut_messages')
    op.drop_index(op.f('ix_shortcut_messages_id'), table_name='shortcut_messages')
    op.drop_table('shortcut_messages')
