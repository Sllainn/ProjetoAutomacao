import os
from logging.config import fileConfig

from sqlalchemy import create_engine
from alembic import context

# Importe a Base dos seus models para o Alembic mapear as tabelas
from app.models import Base

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_database_url():
    """Obtém a URL do banco, priorizando o ambiente e ajustando o driver."""
    # A URL contém %%40 para evitar conflitos de interpolação se lida estaticamente
    fallback_url = "postgresql+psycopg://postgres.iwwyurdpjhiafysysrtm:2loe4v8i%%40Lti@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
    
    url = os.getenv("DATABASE_URL", fallback_url)
    
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        
    return url

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_database_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    url = get_database_url()
    
    # Criamos a engine diretamente aqui. Isso evita o uso do engine_from_config
    # e impede que o Python tente interpretar o '%' da sua senha, resolvendo o erro.
    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()