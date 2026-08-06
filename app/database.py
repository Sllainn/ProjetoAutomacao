from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Configuração fixa e isolada (sem ler o .env para evitar qualquer caractere corrompido)
DB_USER = "postgres"
DB_PASSWORD = "2loe4v8i@Lti"  # Senha com o @ isolada sem afetar a URL
DB_HOST = "localhost"
DB_PORT = "5433"
DB_NAME = "fett_ia"

# Usamos a forma estruturada de URL do SQLAlchemy para que ele trate a senha de forma segura
from sqlalchemy.engine import URL

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

# Adicione ao final do seu app/database.py

def get_db():
    """Gerador de sessão do banco de dados para injeção de dependência no FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()