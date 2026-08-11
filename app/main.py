import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, Header, HTTPException, status
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.webhook import router as webhook_router
from app.worker import executar_worker_ciclo
from app.database import SessionLocal
from app.services import sincronizacao_completa_banco, renovar_canais_expirando
from app.config import settings

notificacoes_recentes = {}
JANELA_SEGURA_SEGUNDOS = 10 
URL_PUBLICA_NGROK = "https://sublet-detest-cash.ngrok-free.dev" 

def tarefas_agendadas():
    print("⏰ Iniciando rotina de segurança programada...")
    db = SessionLocal()
    try:
        sincronizacao_completa_banco()
        renovar_canais_expirando(db, webhook_url_base=URL_PUBLICA_NGROK)
    finally:
        db.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = BackgroundScheduler()
    scheduler.add_job(tarefas_agendadas, 'interval', hours=6)
    scheduler.add_job(executar_worker_ciclo, 'interval', seconds=15, id="worker_ciclo_job", replace_existing=True)
    
    scheduler.start()
    print("⏱️ APScheduler iniciado! Sincronização e Worker ativos em background.")
    
    yield  
    
    scheduler.shutdown()
    print("🛑 APScheduler desligado.")

app = FastAPI(title="FETT Calendar & WhatsApp Sync API", lifespan=lifespan)

app.include_router(webhook_router)

@app.get("/")
def home():
    return {"status": "API online e operando"}

@app.get("/health")
async def health():
    db = SessionLocal()
    try:
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
            return {"status": "ignorado", "motivo": "webhook duplicado"}
        notificacoes_recentes[x_goog_message_number] = agora

    if x_goog_resource_state == "sync":
        return {"status": "ok"}

    if x_goog_resource_state == "exists":
        background_tasks.add_task(sincronizacao_completa_banco)
        return {"status": "sincronizacao_iniciada"}

    return {"status": "ignorado"}