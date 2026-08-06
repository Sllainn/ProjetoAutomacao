from google.oauth2 import service_account
from googleapiclient.discovery import build

# 1. Caminho para o arquivo JSON que você baixou
CAMINHO_JSON = 'app-sincronizacao-calendario-6fc8146367e1.json' # <-- Mude para o nome do arquivo que você baixou

# 2. O e-mail da agenda que você quer ler (geralmente o seu próprio e-mail do Gmail)
CALENDAR_ID = 'fettadvogados@gmail.com' # <-- Mude para o e-mail da sua agenda

# Configurando a autenticação
escopos = ['https://www.googleapis.com/auth/calendar']
credenciais = service_account.Credentials.from_service_account_file(
    CAMINHO_JSON, scopes=escopos)

# Construindo a conexão com o Google
servico = build('calendar', 'v3', credentials=credenciais)

print("Tentando conectar com o Google Calendar...")

try:
    # Puxando os 5 próximos eventos da sua agenda
    eventos_result = servico.events().list(
        calendarId=CALENDAR_ID, 
        maxResults=5, 
        singleEvents=True,
        orderBy='startTime'
    ).execute()

    eventos = eventos_result.get('items', [])

    if not eventos:
        print('Conexão feita com sucesso! Mas não há eventos futuros na agenda.')
    else:
        print('SUCESSO! Aqui estão os seus próximos eventos:')
        for evento in eventos:
            inicio = evento['start'].get('dateTime', evento['start'].get('date'))
            print(f"- {inicio}: {evento.get('summary', 'Sem Título')}")

except Exception as e:
    print(f"Ops, deu erro: {e}")