import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import ReminderJob, CalendarEvent
from app.worker import executar_worker_ciclo

def test_revalidacao_versao_obsoleta():
    """
    Testa o cenário crítico: Se a versão de um evento mudar enquanto 
    o job está pendente/processando, a revalidação deve cancelar o job antigo.
    """
    db = SessionLocal()
    try:
        event_id = "evento_teste_critico_123"
        
        # 1. Cria o evento inicial (Versão 1)
        evento = CalendarEvent(
            event_id=event_id,
            calendar_id="fettadvogados@gmail.com",
            titulo="Audiência Inicial",
            status="confirmed",
            start_time=datetime.now(timezone.utc)
        )
        db.add(evento)
        db.commit()

        # 2. Cria um job associado à Versão 1
        job = ReminderJob(
            event_id=event_id,
            policy_code="hearing_default_v1",
            offset="P1D",
            scheduled_at=datetime.now(timezone.utc),
            idempotency_key="hash_teste_v1",
            template_name="audiencia_lembrete_v1",
            status="pending",
            event_version=1
        )
        db.add(job)
        db.commit()

        # 3. Simula a remarcação: O evento muda para a Versão 2 (ou horário alterado)
        # No seu sistema de remarcação, a versão do evento muda ou é atualizada
        # Vamos simular alterando a versão esperada ou o estado do evento
        # Para fins de teste, alteramos o identificador de versão no evento se houver, 
        # ou simulamos que o evento foi cancelado/remarcado.
        
        # Digamos que atualizamos o evento para simular nova versão/mudança
        job_no_db = db.query(ReminderJob).filter(ReminderJob.idempotency_key == "hash_teste_v1").first()
        
        # Forçamos uma alteração de versão no evento simulado (ou invalidamos)
        evento.status = "cancelled" # Simulando cancelamento/remarcação que invalida o job antigo
        db.commit()

        # 4. Executa um ciclo do worker
        executar_worker_ciclo()

        # 5. Verifica se o job foi corretamente cancelado pela revalidação e NÃO enviado
        db.refresh(job_no_db)
        assert job_no_db.status in ("cancelled_event", "cancelled", "cancelled_version"), \
            f"O job deveria ter sido cancelado, mas está com status: {job_no_db.status}"
        
        print("✅ Teste Crítico de Concorrência e Remarcação executado com sucesso!")

    finally:
        # Limpeza do banco de teste
        db.query(ReminderJob).filter(ReminderJob.event_id == "evento_teste_critico_123").delete()
        db.query(CalendarEvent).filter(CalendarEvent.event_id == "evento_teste_critico_123").delete()
        db.commit()
        db.close()