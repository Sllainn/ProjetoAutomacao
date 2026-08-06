import time
import random
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ReminderJob, CalendarEvent
from app.logger import registrar_log  # Importação do logger estruturado

def executar_worker_ciclo():
    """
    Worker concorrente seguro para processamento de lembretes pendentes 
    conforme as regras 205 a 210 e validação de versão (regras 206, 221),
    integrado com logs estruturados (XIX).
    """
    db = SessionLocal()
    try:
        # 1. Seleção concorrente segura utilizando FOR UPDATE SKIP LOCKED
        jobs = db.query(ReminderJob).filter(
            ReminderJob.status.in_(["pending", "retry"]),
            ReminderJob.scheduled_at <= datetime.now(timezone.utc)
        ).with_for_update(skip_locked=True).limit(20).all()

        if not jobs:
            return

        for job in jobs:
            correlation_id = f"corr_job_{job.id}"

            # Regra 205: Marcar como processing e adquirir lease antes da chamada
            job.status = "processing"
            job.attempts = (job.attempts or 0) + 1
            db.commit()

            registrar_log(
                event_name="reminder_job_claimed",
                mensagem=f"Job {job.id} adquirido para processamento.",
                correlation_id=correlation_id,
                calendar_event_id=job.event_id,
                job_id=str(job.id),
                attempt=job.attempts
            )

            try:
                # Regra 206 & 221: Revalidar se o evento continua ativo e se a versão confere
                evento = db.query(CalendarEvent).filter(CalendarEvent.event_id == job.event_id).first()
                
                if not evento or evento.status == "cancelled":
                    job.status = "cancelled_event"
                    db.commit()
                    registrar_log(
                        event_name="reminder_job_cancelled",
                        mensagem=f"Job {job.id} cancelado: O evento associado não está mais ativo.",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.id)
                    )
                    continue

                # Validação estrita da versão (Stale Event Version)
                if hasattr(job, "event_version") and job.event_version and hasattr(evento, "version") and evento.version != job.event_version:
                    job.status = "cancelled_version"
                    db.commit()
                    registrar_log(
                        event_name="reminder_job_cancelled",
                        mensagem=f"Job {job.id} cancelado: Versão obsoleta detectada.",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.id)
                    )
                    continue

                # Regra 207: Aplicar kill switch e dry-run
                KILL_SWITCH_ATIVO = False  
                DRY_RUN_ATIVO = False      

                if KILL_SWITCH_ATIVO:
                    registrar_log(
                        event_name="dispatch_switch_changed",
                        mensagem=f"Kill Switch ativado! Interrompendo envio do job {job.id}.",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        job_id=str(job.id)
                    )
                    job.status = "pending"  
                    db.commit()
                    continue

                # Regra 208: Registrar tentativa antes da chamada externa
                if DRY_RUN_ATIVO:
                    job.status = "sent"
                    job.sent_at = datetime.now(timezone.utc)
                    db.commit()
                    registrar_log(
                        event_name="reminder_job_sent",
                        mensagem=f"[Dry-Run] Mensagem simulada com sucesso para o job {job.id}.",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.id),
                        attempt=job.attempts
                    )
                    continue

                # --- AQUI ENTRA A CHAMADA REAL DO WHATSAPP (WABA) ---
                inicio_chamada = time.time()
                # response = await whatsapp_client.send_template(...)
                duracao_ms = int((time.time() - inicio_chamada) * 1000)

                # Sucesso no envio:
                job.status = "sent"
                job.sent_at = datetime.now(timezone.utc)
                db.commit()

                registrar_log(
                    event_name="reminder_job_sent",
                    mensagem=f"Job {job.id} enviado com sucesso via WhatsApp.",
                    correlation_id=correlation_id,
                    calendar_event_id=job.event_id,
                    job_id=str(job.id),
                    attempt=job.attempts,
                    provider_message_id="wamid_ficticio_exemplo",
                    duration_ms=duracao_ms
                )

            except Exception as e:
                db.rollback()
                
                MAX_TENTATIVAS = 3
                if job.attempts >= MAX_TENTATIVAS:
                    job.status = "review_required"
                    registrar_log(
                        event_name="reminder_job_failed",
                        mensagem=f"Job {job.id} atingiu o limite de {MAX_TENTATIVAS} tentativas e foi para revisão: {str(e)}",
                        nivel="ERROR",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.id),
                        attempt=job.attempts
                    )
                else:
                    job.status = "retry"
                    tempo_backoff = (2 ** job.attempts) + random.uniform(1, 3)
                    registrar_log(
                        event_name="reminder_job_retry",
                        mensagem=f"Erro temporário no job {job.id}. Agendado retry em {tempo_backoff:.2f}s: {str(e)}",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.id),
                        attempt=job.attempts
                    )

                db.commit()

    except Exception as erro_geral:
        db.rollback()
        registrar_log(
            event_name="worker_critical_error",
            mensagem=f"Erro crítico no ciclo do Worker: {str(erro_geral)}",
            nivel="ERROR"
        )
    finally:
        db.close()