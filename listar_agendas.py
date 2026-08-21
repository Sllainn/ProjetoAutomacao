import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Carrega as variáveis do arquivo .env
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REL_JSON_PATH = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON', 'config/credentials.json')
CAMINHO_JSON = os.path.join(BASE_DIR, REL_JSON_PATH)

EMAIL_AGENDA = os.getenv('GOOGLE_CALENDAR_ID')

if not EMAIL_AGENDA:
    raise ValueError("A variável de ambiente GOOGLE_CALENDAR_ID não foi definida no arquivo .env.")

if not os.path.exists(CAMINHO_JSON):
    raise FileNotFoundError(f"Arquivo de credenciais não encontrado em: {CAMINHO_JSON}")

credenciais = service_account.Credentials.from_service_account_file(
    CAMINHO_JSON, 
    scopes=['https://www.googleapis.com/auth/calendar']
)

servico = build('calendar', 'v3', credentials=credenciais)

print(" Varrendo TODAS as páginas de eventos da agenda configurada via ENV...\n")

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

print(f"\n Concluído! Total de {total_encontrados} eventos encontrados.")