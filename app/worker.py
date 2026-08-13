import time
import random
import asyncio
import os
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ReminderJob, CalendarEvent
from app.logger import registrar_log  
from app.whatsapp import OfficialWhatsAppClient

def executar_worker_ciclo():
    """
    Worker concorrente seguro para processamento de lembretes pendentes 
    conforme as regras 205 a 210 e validação de versão (regras 206, 221),
    integrado com logs estruturados (XIX) e envio real via WABA (OfficialWhatsAppClient).
    """
    db = SessionLocal()
    try:
        # 1. Seleção concorrente segura utilizando FOR UPDATE SKIP LOCKED
        jobs = db.query(ReminderJob).filter(
            ReminderJob.status.in_(["pending", "retry", "PENDING", "RETRY"]),
            ReminderJob.scheduled_time <= datetime.now(timezone.utc)
        ).with_for_update(skip_locked=True).limit(20).all()

        if not jobs:
            return

        for job in jobs:
            correlation_id = f"corr_job_{job.job_id}"

            # Regra 205: Marcar como processing e atualizar attempt_count
            job.status = "processing"
            job.attempt_count = (job.attempt_count or 0) + 1
            db.commit()

            registrar_log(
                event_name="reminder_job_claimed",
                mensagem=f"Job {job.job_id} adquirido para processamento.",
                correlation_id=correlation_id,
                calendar_event_id=job.event_id,
                job_id=str(job.job_id),
                attempt=job.attempt_count
            )

            try:
                # Regra 206 & 221: Revalidar se o evento continua ativo e se a versão confere
                evento = db.query(CalendarEvent).filter(CalendarEvent.event_id == job.event_id).first()
                
                if not evento or evento.status == "cancelled":
                    job.status = "cancelled_event"
                    db.commit()
                    registrar_log(
                        event_name="reminder_job_cancelled",
                        mensagem=f"Job {job.job_id} cancelado: O evento associado não está mais ativo.",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.job_id)
                    )
                    continue

                # Validação estrita da versão (Stale Event Version)
                if hasattr(job, "event_version") and job.event_version and hasattr(evento, "version") and evento.version != job.event_version:
                    job.status = "cancelled_version"
                    db.commit()
                    registrar_log(
                        event_name="reminder_job_cancelled",
                        mensagem=f"Job {job.job_id} cancelado: Versão obsoleta detectada.",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.job_id)
                    )
                    continue

                # Regra 207: Aplicar kill switch e dry-run
                KILL_SWITCH_ATIVO = False  
                DRY_RUN_ATIVO = False       

                if KILL_SWITCH_ATIVO:
                    registrar_log(
                        event_name="dispatch_switch_changed",
                        mensagem=f"Kill Switch ativado! Interrompendo envio do job {job.job_id}.",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        job_id=str(job.job_id)
                    )
                    job.status = "pending"  
                    db.commit()
                    continue

                # Regra 208: Registrar tentativa antes da chamada externa
                if DRY_RUN_ATIVO:
                    job.status = "sent"
                    db.commit()
                    registrar_log(
                        event_name="reminder_job_sent",
                        mensagem=f"[Dry-Run] Mensagem simulada com sucesso para o job {job.job_id}.",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.job_id),
                        attempt=job.attempt_count
                    )
                    continue

                # --- CHAMADA REAL DO WHATSAPP (WABA) UTILIZANDO A CLASSE OFICIAL ---
                api_url = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v17.0/127302942258599/messages")
                
                # 🔥 TESTE DEFINITIVO: TOKEN CHUMBADO NO CÓDIGO (Hardcoded)
                # Apague o texto abaixo e cole o seu token real inteiro, mantendo dentro das aspas!
                token = "EAAXiiuB2fKkBSGro3hbmKcu2VowV4aCpH0mH34D9j7yCfRCUQrllXvkvPTxrbY8C1EmLZBEyyZCHVPs636DkvKMBZCsW9PZByFDWXQQ6NgM8GDQ0Y5lKG2ZBtdecopYbT1qPdwTC6Nfch2TyOUro04umZAMP0DM1xU46Hx3qywSaUd4BXir34dH78tYqyqD4RawQZDZD"
                
                whatsapp_client = OfficialWhatsAppClient(api_url=api_url, token=token)

                inicio_chamada = time.time()
                
                # Executa o envio assíncrono para o número do escritório configurado
                send_result = asyncio.run(whatsapp_client.send_template(
                    phone_e164="5551989128092",  
                    template_name="lembrete_audiencia_v1",
                    language="pt_BR",
                    parameters=[evento.titulo if evento else "Audiencia"],
                    idempotency_key=job.idempotency_key
                ))
                
                duracao_ms = int((time.time() - inicio_chamada) * 1000)

                # Sucesso no envio:
                job.status = "sent"
                db.commit()

                registrar_log(
                    event_name="reminder_job_sent",
                    mensagem=f"Job {job.job_id} enviado com sucesso via WhatsApp WABA.",
                    correlation_id=correlation_id,
                    calendar_event_id=job.event_id,
                    job_id=str(job.job_id),
                    attempt=job.attempt_count,
                    provider_message_id=send_result.message_id,
                    duration_ms=duracao_ms
                )

            except Exception as e:
                db.rollback()
                
                # Captura e imprime o erro detalhado retornado pela requisição ou pela API
                print(f"ERRO DETALHADO WHATSAPP / JOB {job.job_id}: {str(e)}")
                
                MAX_TENTATIVAS = 3
                if job.attempt_count >= MAX_TENTATIVAS:
                    job.status = "review_required"
                    registrar_log(
                        event_name="reminder_job_failed",
                        mensagem=f"Job {job.job_id} atingiu o limite de {MAX_TENTATIVAS} tentativas e foi para revisão: {str(e)}",
                        nivel="ERROR",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.job_id),
                        attempt=job.attempt_count
                    )
                else:
                    job.status = "retry"
                    tempo_backoff = (2 ** job.attempt_count) + random.uniform(1, 3)
                    registrar_log(
                        event_name="reminder_job_retry",
                        mensagem=f"Erro temporário no job {job.job_id}. Agendado retry em {tempo_backoff:.2f}s: {str(e)}",
                        nivel="WARNING",
                        correlation_id=correlation_id,
                        calendar_event_id=job.event_id,
                        job_id=str(job.job_id),
                        attempt=job.attempt_count
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