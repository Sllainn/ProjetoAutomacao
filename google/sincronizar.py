import uuid
from datetime import datetime
from googleapiclient.discovery import build
from autenticar import obter_credenciais
# Importe a conexão com seu banco PostgreSQL aqui (ex: via SQLAlchemy ou psycopg2)
# from database import SessionLocal, EventoModel, SyncStateModel


def sincronizacao_inicial():
    creds = obter_credenciais()
    service = build('calendar', 'v3', credentials=creds)

    print("Iniciando sincronização do google calendar")
    
    page_token = None
    next_sync_token = None

    while True: 
        
        events_result = service.events().list( # Parametros estáveis + showDeleted=True
            calendarId='primary',
            showDeleted=True,
            singleEvents=True,
            pageToken=page_token
        ).execute()

        items = events_result.get('items', [])

        
        for event in items: # Processa os eventos recebidos no PostgreSQL
            event_id = event.get('id')
            status = event.get('status') # 'confirmed', 'tentative', 'cancelled'
            summary = event.get('summary', 'Sem título')
            
            if status == 'cancelled': # Excluído/inativo na tabela
                
                print(f" Evento cancelado/deletado: {event_id}")
            else:
                
                start = event['start'].get('dateTime', event['start'].get('date')) # Upsert (Inserir ou Atualizar) no seu banco
                print(f" Salvando no banco: {summary} ({start})")

        
        page_token = events_result.get('nextPageToken') # Verifica se há mais páginas de resultados nesta carga inicial
        if not page_token:
            
            next_sync_token = events_result.get('nextSyncToken') # Quando a última página é processada, o Google envia o nextSyncToken
            break

   
    if next_sync_token:  # Persistir o nextSyncToken no banco de dados
        # DB.save_sync_token(next_sync_token)
        print(f"\n Sincronização concluída")
        print(f" SyncToken Guardado: {next_sync_token}")

if __name__ == '__main__':
    sincronizacao_inicial()