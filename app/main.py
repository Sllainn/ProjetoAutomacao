import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, Header, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.database import SessionLocal
from app.services import sincronizacao_completa_banco, renovar_canais_expirando
from app.config import settings

# --- Variáveis Globais ---
notificacoes_recentes = {}
JANELA_SEGURA_SEGUNDOS = 10 
# Substitua pela sua URL atual do Ngrok ou puxe de uma variável de ambiente (.env)
URL_PUBLICA_NGROK = "https://sublet-detest-cash.ngrok-free.dev" 

# --- Rotinas de Segundo Plano (Passos 169 e 170) ---
def tarefas_agendadas():
    print("⏰ Iniciando rotina de segurança programada...")
    db = SessionLocal()
    try:
        # 1. Sincronização de Segurança (Passo 170)
        sincronizacao_completa_banco()
        
        # 2. Varredura e Renovação de Canais (Passo 169)
        renovar_canais_expirando(db, webhook_url_base=URL_PUBLICA_NGROK)
    finally:
        db.close()

# Inicia o relógio junto com a API
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    # Agenda a rotina para rodar a cada 6 horas
    scheduler.add_job(tarefas_agendadas, 'interval', hours=6)
    scheduler.start()
    print("⏱️ APScheduler iniciado! Rotinas de segurança ativas.")
    
    yield  # A API fica rodando aqui
    
    scheduler.shutdown()
    print("🛑 APScheduler desligado.")



# --- Inicialização do FastAPI ---
app = FastAPI(title="FETT Calendar & WhatsApp Sync API", lifespan=lifespan)

@app.get("/health")
async def health():
    """
    Endpoint de Healthcheck exigido para homologação no Railway.
    Verifica a saúde do banco sem expor segredos ou detalhes internos.
    """
    db = SessionLocal()
    try:
        # Executa uma query leve para testar a conectividade com o banco usando text()
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unhealthy")
    finally:
        db.close()

    return {
        "status": "ok",
        "environment": getattr(settings, "app_env", "staging"),
        "dispatch_enabled": getattr(settings, "dispatch_enabled", False),
    }

@app.get("/")
def home():
    return {"status": "API online e pronta para webhooks"}

# ==========================================
# HEALTHCHECK (Homologação Railway - Regra 258)
# ==========================================
@app.get("/health")
async def health():
    """
    Endpoint de Healthcheck exigido para homologação no Railway.
    Verifica a saúde do banco sem expor segredos ou detalhes internos.
    """
    db = SessionLocal()
    try:
        # Executa uma query leve para testar a conectividade com o banco
        db.execute("SELECT 1")
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database unhealthy")
    finally:
        db.close()

    return {
        "status": "ok",
        "environment": getattr(settings, "app_env", "staging"),
        "dispatch_enabled": getattr(settings, "dispatch_enabled", False),
    }

# ==========================================
# WEBHOOK DO GOOGLE CALENDAR
# ==========================================
@app.post("/webhook/google-calendar")
async def webhook_google_calendar(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_resource_state: str = Header(None),
    x_goog_channel_id: str = Header(None),
    x_goog_message_number: str = Header(None)
):
    agora = time.time()

    chaves_expiradas = [
        msg_id for msg_id, timestamp in notificacoes_recentes.items() 
        if agora - timestamp > JANELA_SEGURA_SEGUNDOS
    ]
    for chave in chaves_expiradas:
        del notificacoes_recentes[chave]

    if x_goog_message_number:
        if x_goog_message_number in notificacoes_recentes:
            print(f"♻️ Webhook duplicado ignorado! (Msg: {x_goog_message_number})")
            return {"status": "ignorado", "motivo": "webhook duplicado"}
        
        notificacoes_recentes[x_goog_message_number] = agora

    print(f"📥 Header recebido | Estado: {x_goog_resource_state} | Canal: {x_goog_channel_id} | Msg: {x_goog_message_number}")

    if x_goog_resource_state == "sync":
        print("✅ Handshake 'sync' recebido com sucesso!")
        return {"status": "ok"}

    if x_goog_resource_state == "exists":
        print("⚡ Evento alterado/criado! Disparando sincronização...")
        background_tasks.add_task(sincronizacao_completa_banco)
        return {"status": "sincronizacao_iniciada"}

    return {"status": "ignorado"}


# ==========================================
# WEBHOOK DO WHATSAPP (API Oficial)
# ==========================================
class WebhookStatusPayload(BaseModel):
    object: Optional[str] = None
    entry: Optional[List[Dict[str, Any]]] = None

@app.get("/webhook/whatsapp")
async def verificar_webhook_whatsapp(request: Request):
    """Regra 192: Validação da verificação inicial (GET) exigida pela Meta."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    VERIFY_TOKEN_ESPERADO = "seu_token_de_verificacao_seguro"

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN_ESPERADO:
            print("✅ Webhook do WhatsApp verificado com sucesso!")
            return int(challenge) if challenge else ""
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Token de verificação do WhatsApp inválido."
            )
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Parâmetros de verificação ausentes."
    )

@app.post("/webhook/whatsapp")
async def receber_status_whatsapp(payload: WebhookStatusPayload):
    """Regras 193 a 197: Processamento de status e erros de entrega assíncronos."""
    print("📥 Recebido Webhook de Status do WhatsApp.")

    try:
        if payload.object == "whatsapp_business_account":
            for entry in payload.entry or []:
                for change in entry.get("changes", []):
                    value = change.get("value", {})
                    statuses = value.get("statuses", [])
                    
                    for stat in statuses:
                        msg_id = stat.get("id")
                        recipient_id = stat.get("recipient_id")
                        status_provedor = stat.get("status")
                        errors = stat.get("errors", [])

                        print(f"🔄 Status da Mensagem [{msg_id}] para {recipient_id}: {status_provedor}")

                        if errors:
                            for err in errors:
                                error_code = err.get("code")
                                error_message = err.get("title")
                                print(f"❌ Erro do Provedor [{error_code}]: {error_message}")

        return {"status": "received"}

    except Exception as e:
        print(f"⚠️ Erro ao processar webhook de status do WhatsApp: {str(e)}")
        return {"status": "error", "detail": "Processado com ressalvas"}