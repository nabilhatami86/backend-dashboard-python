"""add_ticket_queue_system

Revision ID: 487460ac0762
Revises: 7a4ad7b9e6e6
Create Date: 2026-01-03 11:23:19.732001

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '487460ac0762'
down_revision: Union[str, Sequence[str], None] = '7a4ad7b9e6e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add ticket queue system tables."""

    # Create agent_profiles table
    op.create_table(
        'agent_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('display_name', sa.String(), nullable=False),
        sa.Column('signature', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('online', 'offline', 'busy', 'break', name='agent_status'), nullable=False, server_default='offline'),
        sa.Column('is_available', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('max_concurrent_tickets', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('expertise_tags', sa.String(), nullable=True),
        sa.Column('priority_score', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_activity_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('total_tickets_handled', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_tickets_resolved', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('average_response_time_seconds', sa.Integer(), nullable=True),
        sa.Column('average_resolution_time_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )

    # Create tickets table
    op.create_table(
        'tickets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chat_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'assigned', 'in_progress', 'waiting_customer', 'resolved', 'escalated', 'closed', name='ticket_status'), nullable=False, server_default='pending'),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', 'urgent', name='ticket_priority'), nullable=False, server_default='medium'),
        sa.Column('assigned_agent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_response_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_agent_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id')
    )
    op.create_index(op.f('ix_tickets_created_at'), 'tickets', ['created_at'], unique=False)

    # Create queue_assignments table
    op.create_table(
        'queue_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticket_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('assignment_type', sa.Enum('auto', 'manual', 'claimed', 'transferred', name='assignment_type'), nullable=False),
        sa.Column('assigned_by_id', sa.Integer(), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('unassigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['assigned_by_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['ticket_id'], ['tickets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_queue_assignments_assigned_at'), 'queue_assignments', ['assigned_at'], unique=False)
    op.create_index(op.f('ix_queue_assignments_ticket_id'), 'queue_assignments', ['ticket_id'], unique=False)

    # Create agent_metrics table
    op.create_table(
        'agent_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agent_profile_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), server_default=sa.text('CURRENT_DATE'), nullable=False),
        sa.Column('tickets_assigned', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tickets_resolved', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tickets_transferred', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('tickets_escalated', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('avg_first_response_time', sa.Float(), nullable=True),
        sa.Column('avg_resolution_time', sa.Float(), nullable=True),
        sa.Column('avg_wait_time', sa.Float(), nullable=True),
        sa.Column('total_messages_sent', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_messages_received', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('active_hours', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('total_online_duration_seconds', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('satisfaction_score', sa.Float(), nullable=True),
        sa.Column('efficiency_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['agent_profile_id'], ['agent_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_metrics_agent_profile_id'), 'agent_metrics', ['agent_profile_id'], unique=False)
    op.create_index(op.f('ix_agent_metrics_date'), 'agent_metrics', ['date'], unique=False)


def downgrade() -> None:
    """Downgrade schema: Drop ticket queue system tables."""
    op.drop_index(op.f('ix_agent_metrics_date'), table_name='agent_metrics')
    op.drop_index(op.f('ix_agent_metrics_agent_profile_id'), table_name='agent_metrics')
    op.drop_table('agent_metrics')

    op.drop_index(op.f('ix_queue_assignments_ticket_id'), table_name='queue_assignments')
    op.drop_index(op.f('ix_queue_assignments_assigned_at'), table_name='queue_assignments')
    op.drop_table('queue_assignments')

    op.drop_index(op.f('ix_tickets_created_at'), table_name='tickets')
    op.drop_table('tickets')

    op.drop_table('agent_profiles')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS assignment_type')
    op.execute('DROP TYPE IF EXISTS ticket_priority')
    op.execute('DROP TYPE IF EXISTS ticket_status')
    op.execute('DROP TYPE IF EXISTS agent_status')
