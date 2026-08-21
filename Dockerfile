# Imagem base leve do Python
FROM python:3.11-slim

# Configurações de ambiente para otimizar o Python no Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Define a pasta principal dentro do contêiner
WORKDIR /app

# Copia o arquivo de dependências e instala tudo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código do seu projeto
COPY . .

# Comando padrão (será sobrescrito pelo docker-compose)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
