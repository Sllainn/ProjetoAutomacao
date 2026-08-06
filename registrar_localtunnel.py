# registrar_localtunnel.py
from app.database import SessionLocal
from app.services import registrar_watch_google  # Função que faz o servico.events().watch()

# Cole a URL nova gerada pelo localtunnel (sem barra / no final)
URL_LOCALTUNNEL = "https://sublet-detest-cash.ngrok-free.dev"

db = SessionLocal()

try:
    print(f"🔗 Registrando webhook no Google Calendar para: {URL_LOCALTUNNEL}...")
    resposta = registrar_watch_google(db, webhook_url_base=URL_LOCALTUNNEL)
    print("✅ Webhook registrado com sucesso!")
    print(f"📌 Resposta: {resposta}")
finally:
    db.close()