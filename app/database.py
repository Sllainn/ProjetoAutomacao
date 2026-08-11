import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

# Lê as variáveis do ambiente. Se estiver dentro do Docker, ele pega os valores do .env
# Se rodar direto no Windows (para testes manuais rápidos), usa o localhost/5433 como fallback.
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "2loe4v8i@Lti")
DB_HOST = os.getenv("DB_HOST", "db")  # O Docker usa o nome do serviço "db"
DB_PORT = os.getenv("DB_PORT", "5432") # A porta interna nativa do PostgreSQL no Docker
DB_NAME = os.getenv("DB_NAME", "fett_ia")

# O URL.create trata a senha de forma segura, isolando o @
url_conexao = URL.create(
    drivername="postgresql+psycopg",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME
)

engine = create_engine(url_conexao)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Gerador de sessão do banco de dados para injeção de dependência no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()