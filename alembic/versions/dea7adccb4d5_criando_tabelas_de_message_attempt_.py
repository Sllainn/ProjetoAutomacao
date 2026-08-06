"""criando tabelas de message attempt, webhooks e audit

Revision ID: dea7adccb4d5
Revises: 3c20feceef05
Create Date: 2026-08-03 16:44:04.035820

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'dea7adccb4d5'
down_revision: Union[str, Sequence[str], None] = '3c20feceef05'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Drop dependent tables first (those with FKs)
    op.execute('DROP TABLE IF EXISTS audit_events CASCADE')
    op.execute('DROP TABLE IF EXISTS message_attempts CASCADE')
    op.execute('DROP TABLE IF EXISTS webhook_receipts CASCADE')
    op.execute('DROP TABLE IF EXISTS reminder_jobs CASCADE')
    op.execute('DROP TABLE IF EXISTS reminder_policies CASCADE')
    op.execute('DROP TABLE IF EXISTS contacts CASCADE')
    
    # Create reminder_jobs table
    op.create_table(
        'reminder_jobs',
        sa.Column('job_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('event_id', sa.VARCHAR(length=255), nullable=True),
        sa.Column('resource_id', sa.VARCHAR(length=255), nullable=True),
        sa.Column('status', sa.VARCHAR(length=50), server_default=sa.text("'PENDING'::character varying"), nullable=True),
        sa.Column('scheduled_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('locked_until', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('idempotency_key', sa.VARCHAR(length=255), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['calendar_events.event_id'], name='reminder_jobs_event_id_fkey'),
        sa.ForeignKeyConstraint(['resource_id'], ['calendar_channels.resource_id'], name='reminder_jobs_resource_id_fkey'),
        sa.PrimaryKeyConstraint('job_id', name='reminder_jobs_pkey'),
        sa.UniqueConstraint('idempotency_key', name='reminder_jobs_idempotency_key_key')
    )
    
    # Create reminder_policies table
    op.create_table(
        'reminder_policies',
        sa.Column('policy_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('nome_politica', sa.VARCHAR(length=255), nullable=False),
        sa.Column('versao', sa.INTEGER(), server_default=sa.text('1'), nullable=True),
        sa.Column('is_approved', sa.BOOLEAN(), server_default=sa.text('false'), nullable=True),
        sa.Column('rules_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resource_id', sa.VARCHAR(length=255), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['resource_id'], ['calendar_channels.resource_id'], name='reminder_policies_resource_id_fkey'),
        sa.PrimaryKeyConstraint('policy_id', name='reminder_policies_pkey')
    )
    
    # Create message_attempts table
    op.create_table(
        'message_attempts',
        sa.Column('attempt_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('job_id', sa.VARCHAR(length=255), nullable=True),
        sa.Column('event_id', sa.VARCHAR(length=255), nullable=True),
        sa.Column('version_id', sa.INTEGER(), nullable=True),
        sa.Column('status', sa.VARCHAR(length=50), nullable=False),
        sa.Column('channel', sa.VARCHAR(length=50), nullable=True),
        sa.Column('payload_enviado', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('resposta_sanitizada', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('erro_mensagem', sa.TEXT(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['calendar_events.event_id'], name='message_attempts_event_id_fkey'),
        sa.ForeignKeyConstraint(['job_id'], ['reminder_jobs.job_id'], name='message_attempts_job_id_fkey'),
        sa.ForeignKeyConstraint(['version_id'], ['event_versions.version_id'], name='message_attempts_version_id_fkey'),
        sa.PrimaryKeyConstraint('attempt_id', name='message_attempts_pkey')
    )
    
    # Create webhook_receipts table
    op.create_table(
        'webhook_receipts',
        sa.Column('webhook_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('provider', sa.VARCHAR(length=50), nullable=False),
        sa.Column('dedup_hash', sa.VARCHAR(length=255), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('processed', sa.BOOLEAN(), server_default=sa.text('false'), nullable=True),
        sa.Column('locked_until', postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('webhook_id', name='webhook_receipts_pkey'),
        sa.UniqueConstraint('dedup_hash', name='webhook_receipts_dedup_hash_key')
    )
    
    # Create audit_events table
    op.create_table(
        'audit_events',
        sa.Column('audit_id', sa.VARCHAR(length=255), nullable=False),
        sa.Column('action', sa.VARCHAR(length=100), nullable=False),
        sa.Column('actor', sa.VARCHAR(length=255), nullable=False),
        sa.Column('event_type', sa.VARCHAR(length=50), server_default=sa.text("'DOMAIN'::character varying"), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.VARCHAR(length=45), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('audit_id', name='audit_events_pkey')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('audit_events')
    op.drop_table('webhook_receipts')
    op.drop_table('message_attempts')
    op.drop_table('reminder_policies')
    op.drop_table('reminder_jobs')
