"""add_priority_to_chats

Revision ID: f1a2b3c4d5e6
Revises: b2f8a3c1d4e5, c3f1b2a9d8e7
Create Date: 2026-05-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str]] = ('b2f8a3c1d4e5', 'c3f1b2a9d8e7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Buat enum type dulu (PostgreSQL)
    chat_priority = sa.Enum('low', 'medium', 'high', name='chat_priority')
    chat_priority.create(op.get_bind(), checkfirst=True)

    op.add_column(
        'chats',
        sa.Column(
            'priority',
            sa.Enum('low', 'medium', 'high', name='chat_priority'),
            nullable=True,
            server_default='medium',
        )
    )


def downgrade() -> None:
    op.drop_column('chats', 'priority')
    sa.Enum(name='chat_priority').drop(op.get_bind(), checkfirst=True)
