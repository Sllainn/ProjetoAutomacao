import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import isodate
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session
from app.parser import parsear_descricao_evento

from app.database import SessionLocal
from app.models import CalendarEvent, EventVersion, CalendarChannel, ReminderJob, SyncCursor, Contact

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_JSON = os.path.join(BASE_DIR, 'config', 'app-sincronizacao-calendario-6fc8146367e1.json')
EMAIL_AGENDA = 'fettadvogados@gmail.com'

def obter_servico_google():
    escopos = ['https://www.googleapis.com/auth/calendar']
    credenciais = service_account.Credentials.from_service_account_file(CAMINHO_JSON, scopes=escopos)
    return build('calendar', 'v3', credentials=credenciais)

def registrar_watch_google(db: Session, webhook_url_base: str):
    servico = obter_servico_google()
    channel_id = str(uuid.uuid4())
    url_webhook_completa = f"{webhook_url_base.rstrip('/')}/webhook/google-calendar"

    body = {
        "id": channel_id,
        "type": "web_hook",
        "address": url_webhook_completa
    }

    try:
        resposta = servico.events().watch(calendarId=EMAIL_AGENDA, body=body).execute()

        resource_id = resposta.get('resourceId')
        expiration_ms = int(resposta.get('expiration', 0))
        validade_dt = datetime.fromtimestamp(expiration_ms / 1000.0, tz=timezone.utc)

        novo_canal = CalendarChannel(
            resource_id=resource_id,
            canal_google=channel_id,
            calendar_id=EMAIL_AGENDA,
            validade_calendario=validade_dt
        )

        db.add(novo_canal)
        db.commit()

        print(f"🔗 Watch registrado no Google com sucesso! (Validade: {validade_dt})")
        return resposta

    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao registrar watch no Google: {str(e)}")
        raise e

def build_job_key(event_id: str, event_version: int, policy_code: str, offset: str) -> str:
    raw = f"{event_id}|{event_version}|{policy_code}|{offset}"
    return hashlib.sha256(raw.encode()).hexdigest()

def gerar_tarefas_lembretes_para_evento(db: Session, event_id: str, event_version: int, starts_at: datetime):
    policy_code = "hearing_default_v1"
    # P0D dispara imediatamente na criação; as demais seguem a régua regressiva
    offsets = ["P0D", "P30D", "P7D", "P1D", "PT2H"]

    agora_utc = datetime.now(timezone.utc)

    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    else:
        starts_at = starts_at.astimezone(timezone.utc)

    criadas = 0
    for offset_str in offsets:
        if offset_str == "P0D":
            scheduled_at = agora_utc
        else:
            try:
                duracao = isodate.parse_duration(offset_str)
                scheduled_at = starts_at - duracao
            except Exception as e:
                print(f"⚠️ Erro ao interpretar o offset {offset_str}: {e}")
                continue

            if scheduled_at <= agora_utc:
                continue

        job_pk = f"job_{event_id}_{offset_str}".lower()
        idempotency_key = build_job_key(event_id, event_version, policy_code, offset_str)

        # Checa se o job já existe pela chave primária ou idempotency_key
        job_existente = db.query(ReminderJob).filter(
            (ReminderJob.job_id == job_pk) | (ReminderJob.idempotency_key == idempotency_key)
        ).first()

        if job_existente:
            # Se a versão mudou e o job ainda não foi enviado, atualiza o horário e a chave
            if job_existente.status in ["pending", "retry", "PENDING", "RETRY"]:
                job_existente.event_version = event_version
                job_existente.scheduled_time = scheduled_at
                job_existente.idempotency_key = idempotency_key
            continue

        novo_job = ReminderJob(
            job_id=job_pk,
            event_id=event_id,
            event_version=event_version,
            policy_code=policy_code,
            scheduled_time=scheduled_at,
            idempotency_key=idempotency_key,
            status="pending",
            attempt_count=0
        )
        db.add(novo_job)
        criadas += 1

    if criadas > 0:
        print(f"⏰ {criadas} job(s) de lembrete gerado(s) para o evento {event_id}.")


def sincronizacao_completa_banco():
    db = SessionLocal()

    try:
        servico = obter_servico_google()
        print("🚀 Iniciando Sincronização Incremental/Total do Google Calendar...")

        cursor = db.query(SyncCursor).filter(SyncCursor.calendar_id == EMAIL_AGENDA).first()
        sync_token = cursor.sync_token if cursor else None

        page_token = None
        total_processados = 0

        while True:
            params = {
                'calendarId': EMAIL_AGENDA,
                'showDeleted': True,
                'singleEvents': False,
                'maxResults': 250
            }

            if sync_token:
                params['syncToken'] = sync_token
            if page_token:
                params['pageToken'] = page_token

            try:
                res = servico.events().list(**params).execute()
            except HttpError as err:
                if err.resp.status == 410:
                    print("⚠️ Erro 410: Sync Token expirado. Reiniciando sincronização completa...")
                    if cursor:
                        db.delete(cursor)
                        db.commit()
                    sync_token = None
                    page_token = None
                    continue
                else:
                    raise err

            items = res.get('items', [])
            print(f"📄 Processando lote de {len(items)} eventos...")

            for item in items:
                event_id = item.get('id')
                status = item.get('status')
                descricao_bruta = item.get('description', '')

                start_str = item.get('start', {}).get('dateTime', item.get('start', {}).get('date'))
                end_str = item.get('end', {}).get('dateTime', item.get('end', {}).get('date'))
                timezone_str = item.get('start', {}).get('timeZone', 'UTC')

                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00')) if start_str else None
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00')) if end_str else None

                resultado_parser = parsear_descricao_evento(
                    event_id=event_id,
                    descricao=descricao_bruta,
                    start_dt=start_dt,
                    timezone_str=timezone_str
                )

                if resultado_parser["status"] == "success":
                    print(f"✅ Evento {event_id} estruturado pelo Parser!")
                    dados_validados = resultado_parser["data"]

                    cliente_tel = getattr(dados_validados, 'client_external_id', None)
                    if cliente_tel:
                        contato_db = db.query(Contact).filter(Contact.event_id == event_id).first()
                        if not contato_db:
                            contato_db = Contact(
                                contact_id=f"cnt_{event_id}",
                                event_id=event_id,
                                phone=cliente_tel,
                                name=item.get('summary', 'Cliente')
                            )
                            db.add(contato_db)
                        else:
                            contato_db.phone = cliente_tel
                            contato_db.name = item.get('summary', 'Cliente')
                else:
                    print(f"⚠️ Evento {event_id} (Aviso Parser): {resultado_parser.get('errors')}")

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

                    if status != "cancelled" and start_dt:
                        versao_id = nova_versao.version_id if hasattr(nova_versao, 'version_id') else 1
                        gerar_tarefas_lembretes_para_evento(
                            db=db,
                            event_id=event_id,
                            event_version=versao_id,
                            starts_at=start_dt
                        )
                except Exception as err_versao:
                    print(f"⚠️ Erro ao salvar versão do evento {event_id}: {err_versao}")

                total_processados += 1

            db.commit()

            page_token = res.get('nextPageToken')
            if not page_token:
                next_sync_token = res.get('nextSyncToken')
                if next_sync_token:
                    cursor_atual = db.query(SyncCursor).filter(SyncCursor.calendar_id == EMAIL_AGENDA).first()
                    if not cursor_atual:
                        cursor_atual = SyncCursor(calendar_id=EMAIL_AGENDA, sync_token=next_sync_token)
                        db.add(cursor_atual)
                    else:
                        cursor_atual.sync_token = next_sync_token
                    db.commit()
                break

        print(f"✅ Sincronização concluída com sucesso! Processados: {total_processados}")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro durante a sincronização: {str(e)}")
    finally:
        db.close()

def encerrar_watch_google(db: Session, canal_google: str, resource_id: str):
    servico = obter_servico_google()
    body = {"id": canal_google, "resourceId": resource_id}
    try:
        servico.channels().stop(body=body).execute()
        print(f"🛑 Canal {canal_google} encerrado com sucesso no Google.")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível encerrar o canal {canal_google}: {str(e)}")

def renovar_canais_expirando(db: Session, webhook_url_base: str, horas_margem: int = 24):
    agora = datetime.now(timezone.utc)
    limite_expiracao = agora + timedelta(hours=horas_margem)

    canais_expirando = db.query(CalendarChannel).filter(
        CalendarChannel.status == "ACTIVE",
        CalendarChannel.validade_calendario <= limite_expiracao
    ).all()

    if not canais_expirando:
        return

    for canal_antigo in canais_expirando:
        try:
            registrar_watch_google(db, webhook_url_base)
            encerrar_watch_google(db, canal_antigo.canal_google, canal_antigo.resource_id)
            canal_antigo.status = "RENEWED"
            canal_antigo.renovacao_calendario = agora
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"❌ Falha ao renovar canal: {str(e)}")
