import os
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context
from app.models import Base

# É uma configuração do Alembic, que fornece acesso a valores dentro do arquivo .ini de configuração.
config = context.config

# Logging configuration
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_database_url():
    # A URL contém %%40 para evitar conflitos de interpolação se lida estaticamente
    fallback_url = "postgresql+psycopg://postgres.iwwyurdpjhiafysysrtm:2loe4v8i%%40Lti@aws-0-sa-east-1.pooler.supabase.com:6543/postgres"
    
    url = os.getenv("DATABASE_URL", fallback_url)
    
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        
    return url

def run_migrations_offline() -> None:
    # Roda as migrações no modo offline, gerando scripts SQL sem se conectar ao banco de dados.
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
    # Roda as migrações no modo online, conectando-se ao banco de dados e executando as migrações diretamente.
    url = get_database_url()
    
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