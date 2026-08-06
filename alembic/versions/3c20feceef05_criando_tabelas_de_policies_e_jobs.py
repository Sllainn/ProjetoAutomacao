"""criando tabelas de policies e jobs

Revision ID: 3c20feceef05
Revises: da7b5ce89a71
Create Date: 2026-08-03 14:16:53.237078

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '3c20feceef05'
down_revision: Union[str, Sequence[str], None] = 'da7b5ce89a71'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create reminder_jobs table if it doesn't exist
    op.execute('''
        CREATE TABLE IF NOT EXISTS reminder_jobs (
            job_id VARCHAR(255) PRIMARY KEY,
            event_id VARCHAR(255) REFERENCES calendar_events(event_id),
            resource_id VARCHAR(255) REFERENCES calendar_channels(resource_id),
            status VARCHAR(50) DEFAULT 'PENDING',
            scheduled_at TIMESTAMP WITH TIME ZONE NOT NULL,
            locked_until TIMESTAMP WITH TIME ZONE,
            idempotency_key VARCHAR(255) UNIQUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        )
    ''')
    
    # Create reminder_policies table if it doesn't exist
    op.execute('''
        CREATE TABLE IF NOT EXISTS reminder_policies (
            policy_id VARCHAR(255) PRIMARY KEY,
            nome_politica VARCHAR(255) NOT NULL,
            versao INT DEFAULT 1,
            is_approved BOOLEAN DEFAULT false,
            rules_json JSONB,
            resource_id VARCHAR(255) REFERENCES calendar_channels(resource_id),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        )
    ''')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('reminder_policies', if_exists=True)
    op.drop_table('reminder_jobs', if_exists=True)
