"""init tables

Revision ID: 9f730c5050e6
Revises: 
Create Date: 2025-12-19 16:10:22.205929

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f730c5050e6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create enum types (DO blocks handle already-existing types on dirty DBs)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE user_role AS ENUM ('admin', 'agent');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE chat_channel AS ENUM ('WhatsApp', 'Telegram', 'Email');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE chat_mode AS ENUM ('bot', 'agent', 'paused', 'closed');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE message_sender AS ENUM ('customer', 'agent', 'admin');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE message_status AS ENUM ('sent', 'read');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Create users table (phone column added later in ee001a086c5c)
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR NOT NULL,
            email VARCHAR NOT NULL UNIQUE,
            username VARCHAR NOT NULL UNIQUE,
            password VARCHAR NOT NULL,
            role user_role NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_id ON users (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)")

    # Create chats table (group_id/group_name added later in 5ce1e4e66b2a)
    op.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id SERIAL PRIMARY KEY,
            customer_name VARCHAR NOT NULL,
            customer_phone VARCHAR,
            customer_email VARCHAR,
            customer_address VARCHAR,
            channel chat_channel NOT NULL DEFAULT 'WhatsApp',
            mode chat_mode NOT NULL DEFAULT 'bot',
            online BOOLEAN DEFAULT FALSE,
            unread_count INTEGER DEFAULT 0,
            assigned_agent_id INTEGER REFERENCES users(id),
            last_message_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_chats_id ON chats (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_chats_customer_phone ON chats (customer_phone)")

    # Create messages table
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            sender message_sender NOT NULL,
            status message_status NOT NULL DEFAULT 'sent',
            agent_id INTEGER REFERENCES users(id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_id ON messages (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_messages_chat_id ON messages (chat_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('messages')
    op.drop_table('chats')
    op.drop_table('users')
    op.execute("DROP TYPE message_status")
    op.execute("DROP TYPE message_sender")
    op.execute("DROP TYPE chat_mode")
    op.execute("DROP TYPE chat_channel")
    op.execute("DROP TYPE user_role")
