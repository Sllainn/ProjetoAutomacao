import os
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
import isodate  # Certifique-se de ter instalado: pip install isodate
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError  # Importação para capturar erros específicos do Google
from sqlalchemy.orm import Session
from app.parser import parsear_descricao_evento  # Importação do parser de descrições

from app.database import SessionLocal
from app.models import CalendarEvent, EventVersion, CalendarChannel, ReminderJob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_JSON = os.path.join(BASE_DIR, 'config', 'app-sincronizacao-calendario-6fc8146367e1.json')
EMAIL_AGENDA = 'fettadvogados@gmail.com'

def obter_servico_google():
    escopos = ['https://www.googleapis.com/auth/calendar']
    credenciais = service_account.Credentials.from_service_account_file(CAMINHO_JSON, scopes=escopos)
    return build('calendar', 'v3', credentials=credenciais)

def registrar_watch_google(db: Session, webhook_url_base: str):
    """
    Registra a URL pública do Webhook no Google Calendar para escutar alterações em tempo real.
    """
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

        print(f"🔗 Watch registrado no Google com sucesso!")
        print(f"✅ Canal salvo no PostgreSQL (Validade: {validade_dt})")
        print(f"📍 Webhook URL: {url_webhook_completa}")
        print(f"🔑 Channel ID: {channel_id}")
        print(f"📌 Resource ID: {resource_id}")
        return resposta
    
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao registrar watch no Google: {str(e)}")
        raise e

# --- FUNÇÕES DE GERAÇÃO DE TAREFAS DE LEMBRETES (Regras 198 a 204) ---
def build_job_key(event_id: str, event_version: int, policy_code: str, offset: str) -> str:
    """Regra 202: Cria chave determinística única para garantir idempotência."""
    raw = f"{event_id}|{event_version}|{policy_code}|{offset}"
    return hashlib.sha256(raw.encode()).hexdigest()

def gerar_tarefas_lembretes_para_evento(db: Session, event_id: str, event_version: int, starts_at: datetime):
    """
    Transforma a política aprovada em tarefas persistentes (Regras 198 a 204).
    Não chama o WhatsApp durante a criação (Regra 204).
    """
    policy_code = "hearing_default_v1"
    # Exemplo de cadência baseada na sua especificação da imagem
    offsets = ["P30D", "P7D", "P1D"]
    template_mapping = {
        "P30D": "audiencia_aviso_v1",
        "P7D": "audiencia_lembrete_v1",
        "P1D": "audiencia_lembrete_v1"
    }

    agora_utc = datetime.now(timezone.utc)
    
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    else:
        starts_at = starts_at.astimezone(timezone.utc)

    criadas = 0
    for offset_str in offsets:
        try:
            duracao = isodate.parse_duration(offset_str)
            scheduled_at = starts_at - duracao
        except Exception as e:
            print(f"⚠️ Erro ao interpretar o offset {offset_str}: {e}")
            continue

        # Regra 201: Descartar lembretes cujo horário já passou
        if scheduled_at <= agora_utc:
            continue

        idempotency_key = build_job_key(event_id, event_version, policy_code, offset_str)

        existe = db.query(ReminderJob).filter(ReminderJob.idempotency_key == idempotency_key).first()
        if existe:
            continue

        template_name = template_mapping.get(offset_str, "audiencia_lembrete_v1")

        novo_job = ReminderJob(
            event_id=event_id,
            policy_code=policy_code,
            offset=offset_str,
            scheduled_at=scheduled_at,
            idempotency_key=idempotency_key,
            template_name=template_name,
            status="pending"
        )
        db.add(novo_job)
        criadas += 1

    if criadas > 0:
        print(f"⏰ {criadas} jobs de lembrete gerados com segurança para o evento {event_id}.")


def sincronizacao_completa_banco():
    """
    Função de sincronização que lê e atualiza os eventos no PostgreSQL,
    aplicando o parser estruturado e gerando os jobs de lembrete correspondentes.
    """
    db = SessionLocal()
    
    try:
        servico = obter_servico_google()
        print(f"🚀 Iniciando Sincronização Incremental/Total do Google Calendar...")

        ultimo_evento = db.query(CalendarEvent).filter(CalendarEvent.sync_token.isnot(None)).first()
        sync_token = ultimo_evento.sync_token if ultimo_evento else None

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

            # --- PASSO 168: Tratamento do Erro 410 ---
            try:
                res = servico.events().list(**params).execute()
            except HttpError as err:
                if err.resp.status == 410:
                    print("⚠️ Erro 410: Sync Token expirado ou inválido. Reiniciando sincronização completa...")
                    db.query(CalendarEvent).update({CalendarEvent.sync_token: None})
                    db.commit()
                    sync_token = None
                    page_token = None
                    continue  
                else:
                    raise err
            # ------------------------------------------

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

                # --- APLICAÇÃO DO PARSER (Fase XIV) ---
                resultado_parser = parsear_descricao_evento(
                    event_id=event_id,
                    descricao=descricao_bruta,
                    start_dt=start_dt,
                    timezone_str=timezone_str
                )

                if resultado_parser["status"] == "success":
                    print(f"✅ Evento {event_id} estruturado e validado pelo Parser com sucesso!")
                else:
                    print(f"⚠️ Evento {event_id} requer REVISÃO: {resultado_parser.get('errors')}")

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
                    
                    # --- GERAÇÃO DE TAREFAS DE LEMBRETE (Se o evento estiver ativo e com data válida) ---
                    if status != "cancelled" and start_dt:
                        # Pega o ID da versão recém criada para usar na chave determinística
                        versao_id = nova_versao.id if hasattr(nova_versao, 'id') else 1
                        gerar_tarefas_lembretes_para_evento(
                            db=db,
                            event_id=event_id,
                            event_version=versao_id,
                            starts_at=start_dt
                        )

                except Exception as err_versao:
                    print(f"⚠️ Aviso ao salvar versão para o evento {event_id}: {err_versao}")

                total_processados += 1

            db.commit()

            page_token = res.get('nextPageToken')
            if not page_token:
                next_sync_token = res.get('nextSyncToken')
                if next_sync_token:
                    db.query(CalendarEvent).update({CalendarEvent.sync_token: next_sync_token})
                    db.commit()
                break

        print(f"✅ Sincronização concluída com sucesso! Processados: {total_processados}")

    except Exception as e:
        db.rollback()
        print(f"❌ Erro durante a sincronização: {str(e)}")
    finally:
        db.close()

def encerrar_watch_google(db: Session, canal_google: str, resource_id: str):
    """
    Passo 169 (Parte 1): Encerra um canal antigo no Google de forma educada.
    """
    servico = obter_servico_google()
    body = {
        "id": canal_google,
        "resourceId": resource_id
    }
    
    try:
        servico.channels().stop(body=body).execute()
        print(f"🛑 Canal {canal_google} encerrado com sucesso no Google.")
    except Exception as e:
        print(f"⚠️ Aviso: Não foi possível encerrar o canal {canal_google} no Google: {str(e)}")

def renovar_canais_expirando(db: Session, webhook_url_base: str, horas_margem: int = 24):
    """
    Passo 169 (Parte 2): Procura canais ativos próximos do vencimento e os renova.
    """
    agora = datetime.now(timezone.utc)
    limite_expiracao = agora + timedelta(hours=horas_margem)
    
    canais_expirando = db.query(CalendarChannel).filter(
        CalendarChannel.status == "ACTIVE",
        CalendarChannel.validade_calendario <= limite_expiracao
    ).all()
    
    if not canais_expirando:
        print("✅ Nenhum canal precisando de renovação no momento.")
        return
        
    for canal_antigo in canais_expirando:
        print(f"🔄 Renovando canal {canal_antigo.canal_google} (Vence em: {canal_antigo.validade_calendario})...")
        
        try:
            registrar_watch_google(db, webhook_url_base)
            encerrar_watch_google(db, canal_antigo.canal_google, canal_antigo.resource_id)
            
            canal_antigo.status = "RENEWED"
            canal_antigo.renovacao_calendario = agora
            db.commit()
            
            print(f"✅ Canal renovado com sucesso!")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Falha ao tentar renovar o canal {canal_antigo.canal_google}: {str(e)}")