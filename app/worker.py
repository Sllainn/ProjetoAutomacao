import asyncio
import os
import time
from datetime import datetime, timezone

from app.database import SessionLocal
from app.logger import registrar_log
from app.models import CalendarEvent, Contact, ReminderJob
from app.whatsapp import OfficialWhatsAppClient


def executar_worker_ciclo():
    """
    Worker concorrente seguro para processamento de lembretes pendentes
    conforme as regras 205 a 210 e validação de versão (regras 206, 221),
    integrado com logs estruturados e envio dinâmico via WABA.
    """
    db = SessionLocal()
    try:
        # 1. Seleção concorrente utilizando FOR UPDATE SKIP LOCKED
        jobs = db.query(ReminderJob).filter(
            ReminderJob.status.in_(["pending", "retry", "PENDING", "RETRY"]),
            ReminderJob.scheduled_time <= datetime.now(timezone.utc)
        ).with_for_update(skip_locked=True).limit(20).all()

        if not jobs:
            print("Nenhum job pendente encontrado.")
            return

        print(f"Encontrados {len(jobs)} job(s) para processar.")

        for job in jobs:
            correlation_id = f"corr_job_{job.job_id}"

            #  Marcar como processing e atualizar attempt_count
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
                # Revalidar se o evento continua ativo
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

                # Busca o contato dinamicamente pelo event_id
                contato = db.query(Contact).filter(Contact.event_id == job.event_id).first()
                if not contato or not contato.phone:
                    raise ValueError(f"Nenhum telefone encontrado na tabela contacts para o event_id: {job.event_id}")

                telefone_destino = contato.phone.replace("+", "").replace(" ", "").replace("-", "")

                # Configurações do cliente WhatsApp
                api_url = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v17.0/1175247199008432/messages")
                token = os.getenv("WHATSAPP_TOKEN", "EAAXiiuB2fKkBSGro3hbmKcu2VowV4aCpH0mH34D9j7yCfRCUQrllXvkvPTxrbY8C1EmLZBEyyZCHVPs636DkvKMBZCsW9PZByFDWXQQ6NgM8GDQ0Y5lKG2ZBtdecopYbT1qPdwTC6Nfch2TyOUro04umZAMP0DM1xU46Hx3qywSaUd4BXir34dH78tYqyqD4RawQZDZD")

                whatsapp_client = OfficialWhatsAppClient(api_url=api_url, token=token)

                inicio_chamada = time.time()

                # Formatação dinâmica dos parâmetros do compromisso
                data_evento = evento.start_time.strftime("%d/%m/%Y") if evento and getattr(evento, "start_time", None) else "Data a definir"
                hora_evento = evento.start_time.strftime("%H:%M") if evento and getattr(evento, "start_time", None) else "Hora a definir"
                titulo_evento = evento.titulo if evento and getattr(evento, "titulo", None) else "Compromisso Jurídico"

                print(f"Disparando WhatsApp para {telefone_destino} | Assunto: {titulo_evento} | Data: {data_evento} às {hora_evento}")

                # Executa o envio assíncrono
                send_result = asyncio.run(whatsapp_client.send_template( #template da meta para enviar avisos 
                    phone_e164=telefone_destino,
                    template_name="aviso_agenda_advogado",
                    language="pt_BR",
                    parameters=[
                        titulo_evento,   # Variável {{1}}
                        data_evento,     # Variável {{2}}
                        hora_evento      # Variável {{3}}
                    ],
                    idempotency_key=job.idempotency_key
                ))

                duracao_ms = int((time.time() - inicio_chamada) * 1000)

                job.status = "sent"
                db.commit()

                print(f" Job {job.job_id} enviado com sucesso, Message ID: {send_result.message_id}")

                registrar_log(
                    event_name="reminder_job_sent",
                    mensagem=f"Job {job.job_id} enviado com sucesso via WhatsApp.",
                    correlation_id=correlation_id,
                    calendar_event_id=job.event_id,
                    job_id=str(job.job_id),
                    attempt=job.attempt_count,
                    provider_message_id=send_result.message_id,
                    duration_ms=duracao_ms
                )

            except Exception as e:
                db.rollback()
                print(f" ERRO WHATSAPP JOB {job.job_id}: {e!s}")

                MAX_TENTATIVAS = 3
                if job.attempt_count >= MAX_TENTATIVAS:
                    job.status = "review_required"
                else:
                    job.status = "retry"

                db.commit()

    except Exception as erro_geral:
        db.rollback()
        print(f" Erro crítico no ciclo do Worker: {erro_geral!s}")
    finally:
        db.close()

if __name__ == "__main__":
    executar_worker_ciclo()
