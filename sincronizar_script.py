import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.database import SessionLocal
from app.models import CalendarEvent, EventVersion

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_JSON = os.path.join(BASE_DIR, 'config', 'app-sincronizacao-calendario-6fc8146367e1.json')
EMAIL_AGENDA = 'fettadvogados@gmail.com'

def sincronizacao_completa_banco():
    db = SessionLocal()
    
    try:
        escopos = ['https://www.googleapis.com/auth/calendar']
        credenciais = service_account.Credentials.from_service_account_file(CAMINHO_JSON, scopes=escopos)
        servico = build('calendar', 'v3', credentials=credenciais)

        print(f" Iniciando Google Calendar para: {EMAIL_AGENDA}")

        page_token = None
        total_processados = 0
        pagina = 1

        while True:
            params = {
                'calendarId': EMAIL_AGENDA,
                'showDeleted': True,
                'singleEvents': False,
                'maxResults': 250
            }

            if page_token:
                params['pageToken'] = page_token

            res = servico.events().list(**params).execute()
            items = res.get('items', [])

            print(f" Processando Página {pagina}: {len(items)} eventos lidos...")

            for item in items:
                event_id = item.get('id')
                status = item.get('status')
                
                start_str = item.get('start', {}).get('dateTime', item.get('start', {}).get('date'))
                end_str = item.get('end', {}).get('dateTime', item.get('end', {}).get('date'))
                
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')) if start_str else None
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else None

                evento_db = db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).first()

                if not evento_db:
                    evento_db = CalendarEvent(
                        event_id=event_id,
                        calendar_id=EMAIL_AGENDA,
                        titulo=item.get('summary', 'Sem título'),
                        status=status,
                        start_time=start_dt,
                        end_time=end_dt
                    )
                    db.add(evento_db)
                else:
                    evento_db.titulo = item.get('summary', 'Sem título')
                    evento_db.status = status
                    evento_db.start_time = start_dt
                    evento_db.end_time = end_dt

                db.flush()

                try:
                    nova_versao = EventVersion(
                        event_id=event_id,
                        payload=item
                    )
                    db.add(nova_versao)
                    db.flush()
                except Exception as err_versao:
                    print(f" Aviso: Não foi possível salvar versão para o evento {event_id}: {err_versao}")

                total_processados += 1

            db.commit()

            page_token = res.get('nextPageToken')
            if not page_token:
                break
            
            pagina += 1

        print(f"\n SINCRONIZAÇÃO TOTAL CONCLUÍDA COM SUCESSO!")
        print(f" Total de eventos processados e salvos no PostgreSQL: {total_processados}")

    except Exception as e:
        db.rollback()
        print(f" Erro na sincronização: {str(e)}")
    finally:
        db.close()


if __name__ == '__main__':
    sincronizacao_completa_banco()