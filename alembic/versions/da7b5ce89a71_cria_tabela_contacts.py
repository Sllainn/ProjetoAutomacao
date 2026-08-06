"""cria_tabela_contacts

Revision ID: da7b5ce89a71
Revises: d3a367cd145d
Create Date: 2026-08-03 13:27:28.723213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'da7b5ce89a71'
down_revision: Union[str, Sequence[str], None] = 'd3a367cd145d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # This migration previously dropped contacts, but we'll keep the migration path clean
    # by using CREATE TABLE IF NOT EXISTS for event_versions
    op.execute('''
        CREATE TABLE IF NOT EXISTS event_versions (
            version_id SERIAL PRIMARY KEY,
            event_id VARCHAR(255) NOT NULL REFERENCES calendar_events(event_id),
            payload JSON NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
        )
    ''')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('event_versions', if_exists=True)
