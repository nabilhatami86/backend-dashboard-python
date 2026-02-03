"""add_phone_to_users

Revision ID: ee001a086c5c
Revises: a81cc8b0758a
Create Date: 2026-01-02 21:23:38.223648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ee001a086c5c'
down_revision: Union[str, Sequence[str], None] = 'a81cc8b0758a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN phone VARCHAR;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'phone')
