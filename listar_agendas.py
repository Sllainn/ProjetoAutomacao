import os

from google.oauth2 import service_account
from googleapiclient.discovery import build

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_JSON = os.path.join(BASE_DIR, 'config', 'app-sincronizacao-calendario-6fc8146367e1.json')
EMAIL_AGENDA = 'fettadvogados@gmail.com'

credenciais = service_account.Credentials.from_service_account_file(
    CAMINHO_JSON, 
    scopes=['https://www.googleapis.com/auth/calendar']
)

servico = build('calendar', 'v3', credentials=credenciais)

print(f" Varrendo TODAS as páginas de eventos da agenda: {EMAIL_AGENDA}...\n")

total_encontrados = 0
page_token = None
pagina = 1

while True:
    params = {
        'calendarId': EMAIL_AGENDA,
        'maxResults': 250,      # Traz o máximo possível por página
        'showDeleted': True,    # Inclui cancelados
        'pageToken': page_token
    }

    resposta = servico.events().list(**params).execute()
    eventos = resposta.get('items', [])
    
    print(f" Página {pagina}: {len(eventos)} eventos retornados.")
    total_encontrados += len(eventos)

    for item in eventos:
        summary = item.get('summary', '(Sem título)')
        print(f"   - {summary} (ID: {item.get('id')})")

    page_token = resposta.get('nextPageToken')
    if not page_token:
        break
    pagina += 1

print(f"\n Concluído! Total de {total_encontrados} eventos encontrados no total.")