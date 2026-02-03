"""add_admin_messages_table

Revision ID: e016c0677dfa
Revises: ee001a086c5c
Create Date: 2026-01-02 21:56:36.982430

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e016c0677dfa'
down_revision: Union[str, Sequence[str], None] = 'ee001a086c5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create the message_sender enum type if it doesn't already exist
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE message_sender AS ENUM ('customer', 'agent', 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create admin_messages table
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_messages (
            id SERIAL PRIMARY KEY,
            agent_id INTEGER NOT NULL,
            text VARCHAR NOT NULL,
            sender message_sender NOT NULL,
            sender_name VARCHAR,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Create indexes
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_messages_id ON admin_messages (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_admin_messages_agent_id ON admin_messages (agent_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_admin_messages_agent_id'), table_name='admin_messages')
    op.drop_index(op.f('ix_admin_messages_id'), table_name='admin_messages')
    op.drop_table('admin_messages')
    op.execute("DROP TYPE message_sender")
