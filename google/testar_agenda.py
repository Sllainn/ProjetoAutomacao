from datetime import datetime, timezone

from autenticar import obter_credenciais
from googleapiclient.discovery import build


def testar_lista_eventos():
    # Obtém as credenciais usando o token.json salvo
    creds = obter_credenciais()
    service = build('calendar', 'v3', credentials=creds)

    # Captura a data/hora atual no formato ISO 8601
    agora = datetime.now(timezone.utc).isoformat()
    
    print("Buscando os próximos 10 eventos no calendário principal...\n")
    
    # Executa a chamada do método events().list()
    events_result = service.events().list(
        calendarId='primary',
        timeMin=agora,
        maxResults=10,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])

    if not events:
        print('Nenhum evento futuro encontrado.')
        return

    print("EVENTOS ENCONTRADOS")
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        summary = event.get('summary', 'Sem título')
        print(f" Data/Hora: {start} | Evento: {summary}")

if __name__ == '__main__':
    testar_lista_eventos()