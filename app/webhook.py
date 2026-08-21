import hashlib
import hmac
import os

from fastapi import APIRouter, HTTPException, Request, status

from app.database import SessionLocal
from app.logger import registrar_log
from app.models import ReminderJob

# Usei o prefix="/webhook"
router = APIRouter(prefix="/webhook", tags=["Webhook WhatsApp"])

WEBHOOK_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "irmaosfett704")
META_APP_SECRET = os.getenv("META_APP_SECRET", "seu_app_secret_aqui")


def verificar_assinatura(payload_body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    
    expected_signature = signature_header.split("=")[1]
    
    mac = hmac.new(
        META_APP_SECRET.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    calculated_signature = mac.hexdigest()
    
    return hmac.compare_digest(calculated_signature, expected_signature)


@router.get("")
@router.get("/")
async def verificar_webhook_meta(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == WEBHOOK_VERIFY_TOKEN:
            registrar_log(event_name="webhook_verified", mensagem="Webhook verificado com sucesso pela Meta.", nivel="INFO")
            return int(challenge) if challenge and challenge.isdigit() else challenge
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token de verificação inválido.")
    
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parâmetros inválidos.")


@router.post("")
@router.post("/")
async def receber_evento_webhook(request: Request):
    body_bytes = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not verificar_assinatura(body_bytes, signature):
        registrar_log(event_name="webhook_signature_invalid", mensagem="Assinatura X-Hub-Signature-256 inválida no webhook.", nivel="ERROR")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura inválida.")

    data = await request.json()
    
    db = SessionLocal()
    try:
        entry = data.get("entry", [])
        for ent in entry:
            changes = ent.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                statuses = value.get("statuses", [])
                
                for stat in statuses:
                    wamid = stat.get("id")
                    status_mensagem = stat.get("status")
                    
                    registrar_log(
                        event_name="whatsapp_status_received",
                        mensagem=f"Mensagem {wamid} atualizada para o status: {status_mensagem}",
                        nivel="INFO",
                        provider_message_id=wamid
                    )

                    job = db.query(ReminderJob).filter(ReminderJob.provider_message_id == wamid).first()
                    if job:
                        job.status = status_mensagem
                        db.commit()

        return {"status": "success"}
        
    except Exception as e:
        db.rollback()
        registrar_log(event_name="webhook_processing_error", mensagem=f"Erro ao processar webhook: {e!s}", nivel="ERROR")
        return {"status": "error", "detail": str(e)}
    finally:
        db.close()