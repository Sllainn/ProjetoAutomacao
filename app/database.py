import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

# Prioriza a DATABASE_URL completa que vem do ambiente (Cloud Run / Supabase)
# Caso não ache, monta usando variáveis individuais ou fallback local.
database_url = os.getenv("DATABASE_URL") or settings.database_url

if not database_url:
    # Fallback caso rode localmente sem .env completo
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "2loe4v8i@Lti")
    DB_HOST = os.getenv("DB_HOST", "localhost")  # Ajustado para localhost em vez de 'db'
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "fett_ia")
    database_url = f"postgresql+psycopg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Garante que o driver do SQLAlchemy utilize o psycopg correto
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine = create_engine(database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Gerador de sessão do banco de dados para injeção de dependência no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()