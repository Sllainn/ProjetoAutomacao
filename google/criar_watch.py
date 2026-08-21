import uuid

from autenticar import obter_credenciais
from googleapiclient.discovery import build

# Importe sua sessão do banco de dados 

def criar_canal_watch():
    creds = obter_credenciais()
    service = build('calendar', 'v3', credentials=creds)

    # Gera um ID único para este canal
    channel_id = str(uuid.uuid4())
    
    # URL HTTPS do seu webhook que receberá as notificações do Google
    WEBHOOK_URL = "https://loud-frogs-happen.loca.lt/t/webhook/google-calendar"

    body = {
        'id': channel_id,
        'type': 'web_hook',
        'address': WEBHOOK_URL,
    }

    try:
        # Executa o events().watch() na agenda principal
        resposta = service.events().watch(
            calendarId='primary',
            body=body
        ).execute()

        resource_id = resposta.get('resourceId')
        expiration = resposta.get('expiration') # Timestamp de expiração em ms

        print(" Canal de Webhook criado")
        print(f" Channel ID: {channel_id}")
        print(f" Resource ID: {resource_id}")
        print(f" Expiration (ms): {expiration}")

    except Exception as e:
        print(f" Erro ao criar canal watch: {e}")

if __name__ == '__main__':
    criar_canal_watch()