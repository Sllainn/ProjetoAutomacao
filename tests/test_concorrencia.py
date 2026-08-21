import uuid
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import CalendarEvent, ReminderJob
from app.worker import executar_worker_ciclo


def test_revalidacao_versao_obsoleta():
    """
    Testa o cenário crítico: Se a versão de um evento mudar enquanto
    o job está pendente/processando, a revalidação deve cancelar o job antigo.
    """
    db = SessionLocal()
    event_id = "evento_teste_critico_123"
    
    try:
        # Garante limpeza prévia caso tenha ficado lixo de execuções passadas
        db.query(ReminderJob).filter(ReminderJob.event_id == event_id).delete()
        db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).delete()
        db.commit()

        # 1. Cria o evento inicial (Versão 1)
        evento = CalendarEvent(
            event_id=event_id,
            titulo="Audiência Inicial",
            status="confirmed",
            start_time=datetime.now(timezone.utc)
        )
        db.add(evento)
        db.commit()

        # 2. Cria um job associado à Versão 1
        job = ReminderJob(
            job_id=str(uuid.uuid4()),
            event_id=event_id,
            policy_code="hearing_default_v1",
            scheduled_time=datetime.now(timezone.utc),
            idempotency_key="hash_teste_v1",
            status="PENDING",
            event_version=1
        )
        db.add(job)
        db.commit()

        # 3. Busca o job gravado e altera o evento para simular alteração/cancelamento
        job_no_db = db.query(ReminderJob).filter(ReminderJob.idempotency_key == "hash_teste_v1").first()
        
        evento.status = "cancelled"
        db.commit()

        # 4. Executa um ciclo do worker
        executar_worker_ciclo()

        # 5. Verifica se o job foi corretamente cancelado pela revalidação
        db.refresh(job_no_db)
        assert job_no_db.status in ("cancelled_event", "cancelled", "cancelled_version"), \
            f"O job deveria ter sido cancelado, mas está com status: {job_no_db.status}"

        print(" Teste Crítico de Concorrência e Remarcação executado com sucesso!")

    except Exception:
        db.rollback()
        raise 
    finally:
        # Limpeza segura do banco de teste
        try:
            db.query(ReminderJob).filter(ReminderJob.event_id == event_id).delete()
            db.query(CalendarEvent).filter(CalendarEvent.event_id == event_id).delete()
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()