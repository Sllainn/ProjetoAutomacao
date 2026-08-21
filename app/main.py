import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, BackgroundTasks, Header, HTTPException, status
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.webhook import router as webhook_router
from app.worker import executar_worker_ciclo
from app.database import SessionLocal
from app.services import sincronizacao_completa_banco, renovar_canais_expirando
from app.config import settings
from app.models import Contact, CalendarEvent

notificacoes_recentes = {}
JANELA_SEGURA_SEGUNDOS = 10 
URL_PUBLICA_NGROK = "https://sublet-detest-cash.ngrok-free.dev" 

def tarefas_agendadas():
    print("Iniciando rotina de segurança programada")
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
    print(" APScheduler iniciado, sincronização e worker ativos.")
    
    yield  
    
    scheduler.shutdown()
    print(" APScheduler desligado.")

# redirect_slashes=False evita que o FastAPI bloqueie ou mude requisições GET
app = FastAPI(title="FETT Calendar & WhatsApp Sync API", lifespan=lifespan, redirect_slashes=False)

# Inclui os endpoints do WhatsApp (/webhook)
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

@app.post("/webhook/liderhub")
async def webhook_liderhub(request: Request):
    try:
        dados = await request.json()
        print(f"Payload recebido do Liderhub: {dados}")
        
        nome = dados.get("nome") or "Lead Liderhub"
        telefone = dados.get("celular")
        
        # Trava de segurança para ignorar o teste vazio do LiderHub
        if not telefone or telefone == '<celular>':
            print(" Webhook ignorado: Payload de teste sem dados reais.")
            return {"status": "ignorado", "motivo": "Payload de teste"}
            
        telefone_limpo = "".join(c for c in str(telefone) if c.isdigit())
        
        db = SessionLocal()
        try:
            fake_event_id = f"lead_{uuid.uuid4().hex[:8]}"
            
            # 1. Cria o evento fantasma primeiro
            novo_evento = CalendarEvent(
                event_id=fake_event_id,
                calendar_id="liderhub_api",
                titulo=f"Lead: {nome}",
                status="confirmed",
                start_time=datetime.now(timezone.utc),
                end_time=datetime.now(timezone.utc)
            )
            db.add(novo_evento)
            db.flush() 
            
            # 2. Cria o contato em seguida
            novo_contato = Contact(
                contact_id=f"cnt_{fake_event_id}",
                event_id=fake_event_id,
                name=nome,
                phone=telefone_limpo
            )
            db.add(novo_contato)
            
            db.commit() 
            print(f" Lead do Liderhub salvo com sucesso: {nome} - {telefone_limpo}")
            
        except Exception as db_err:
            db.rollback()
            raise db_err
        finally:
            db.close()
            
        return {"status": "sucesso"}
        
    except Exception as e:
        print(f" Erro ao processar webhook do Liderhub: {e}")
        return {"status": "erro", "detalhe": str(e)}