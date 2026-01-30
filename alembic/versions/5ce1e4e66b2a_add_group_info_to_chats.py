"""add_group_info_to_chats

Revision ID: 5ce1e4e66b2a
Revises: 487460ac0762
Create Date: 2026-01-30 14:14:20.466463

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ce1e4e66b2a'
down_revision: Union[str, Sequence[str], None] = '487460ac0762'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add group_id and group_name columns to chats table
    op.add_column('chats', sa.Column('group_id', sa.String(), nullable=True))
    op.add_column('chats', sa.Column('group_name', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Remove group_id and group_name columns from chats table
    op.drop_column('chats', 'group_name')
    op.drop_column('chats', 'group_id')
