# 1. Imagem base leve do Python
FROM python:3.11-slim

# 2. Configurações de ambiente para otimizar o Python no Docker
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Define a pasta principal dentro do contêiner
WORKDIR /app

# 4. Copia o arquivo de dependências e instala tudo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copia o resto do código do seu projeto
COPY . .

# 6. Comando padrão (será sobrescrito pelo docker-compose)
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
