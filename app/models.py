from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


#Aqui guardamos as tabelas do banco de dados, incluindo eventos, contatos, políticas de lembrete, trabalhos de lembrete, tentativas de envio de mensagens, recibos de webhook e eventos de auditoria.
class Base(DeclarativeBase):
    pass


class CalendarChannel(Base):
    __tablename__ = "calendar_channels"

    resource_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    canal_google: Mapped[str] = mapped_column(String(250), nullable=False)
    calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE")
    
    validade_calendario: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    renovacao_calendario: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SyncCursor(Base):
    __tablename__ = "sync_cursors"
    
    calendar_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    sync_token: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    # Ajustado para aceitar nulo caso o canal não esteja pré-cadastrado na tabela calendar_channels
    calendar_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_channels.resource_id", ondelete="SET NULL"), nullable=True)
    titulo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventVersion(Base):
    __tablename__ = "event_versions"

    version_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(255), ForeignKey("calendar_events.event_id"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contact(Base):
    __tablename__ = "contacts"

    contact_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_events.event_id"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    event = relationship("CalendarEvent", backref="contacts")


class ReminderPolicies(Base):
    __tablename__ = "reminder_policies"

    policy_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    event_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_events.event_id"), nullable=True)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    rules_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_channels.resource_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReminderJob(Base):
    __tablename__ = "reminder_jobs"

    job_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_channels.resource_id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_events.event_id"), nullable=True)
    
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    policy_code: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), default="PENDING")
    scheduled_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    
    provider_message_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MessageAttempt(Base):
    __tablename__ = "message_attempts"

    attempt_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("reminder_jobs.job_id"), nullable=True)
    event_id: Mapped[str | None] = mapped_column(String(255), ForeignKey("calendar_events.event_id"), nullable=True)
    version_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("event_versions.version_id"), nullable=True)
    
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payload_enviado: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    resposta_sanitizada: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    erro_mensagem: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"

    webhook_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    audit_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), default="DOMAIN")
    audit_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ArmazenaDados(Base):
    __tablename__ = "armazena_dados"

    id_save = Column(String(255), primary_key=True, index=True)
    resource_id = Column(String(255), ForeignKey("calendar_channels.resource_id"))
    event_id = Column(String(255), ForeignKey("calendar_events.event_id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())