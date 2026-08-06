import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any

# Configuração base do logger do sistema
logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger("fett_sync")
logger.handlers = []  # Remove handlers padrão para evitar logs duplicados

# ALLOWLIST de campos estritamente permitidos nos logs estruturados
CAMPOS_PERMITIDOS = {
    "timestamp",
    "level",
    "event",
    "environment",
    "message",
    "correlation_id",
    "calendar_event_id",
    "job_id",
    "attempt",
    "provider_message_id",
    "duration_ms",
    "error_code",
    "status"
}

def sanitizar_dados(extras: Dict[str, Any]) -> Dict[str, Any]:
    """
    Aplica a regra de Allowlist e Redaction para impedir vazamento de dados sensíveis.
    Remove campos desconhecidos ou confidenciais (ex: telefones, payloads brutos).
    """
    dados_limpos = {}
    for chave, valor in extras.items():
        if chave in CAMPOS_PERMITIDOS:
            # Se houver string parecida com telefone ou token, podemos mascarar (Redaction)
            if isinstance(valor, str) and ("token" in chave.lower() or "secret" in chave.lower()):
                dados_limpos[chave] = "[REDACTED]"
            else:
                dados_limpos[chave] = valor
    return dados_limpos

class StructuredJsonFormatter(logging.Formatter):
    """
    Formatador para garantir logs em formato JSON estrito, 
    filtrando apenas campos permitidos.
    """
    def format(self, record: logging.LogRecord) -> str:
        dados_extras = getattr(record, "extra_data", {})
        dados_filtrados = sanitizar_dados(dados_extras)
        
        log_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "event": getattr(record, "event_name", "application_log"),
            "environment": "staging",
            "message": record.getMessage(),
            **dados_filtrados
        }
        
        # Garante que as chaves finais também obedeçam rigorosamente à allowlist
        log_final = {k: v for k, v in log_payload.items() if k in CAMPOS_PERMITIDOS}
        
        return json.dumps(log_final, ensure_ascii=False)

# Adiciona o formatador ao handler
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(StructuredJsonFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

def registrar_log(
    event_name: str, 
    mensagem: str, 
    nivel: str = "INFO", 
    correlation_id: Optional[str] = None,
    calendar_event_id: Optional[str] = None,
    job_id: Optional[str] = None,
    attempt: Optional[int] = None,
    provider_message_id: Optional[str] = None,
    duration_ms: Optional[int] = None,
    extras: Optional[Dict[str, Any]] = None
):
    """
    Função centralizada de log estruturado com bloqueio automático de dados confidenciais.
    """
    extra_data = {}
    if correlation_id:
        extra_data["correlation_id"] = correlation_id
    if calendar_event_id:
        extra_data["calendar_event_id"] = calendar_event_id
    if job_id:
        extra_data["job_id"] = str(job_id)
    if attempt is not None:
        extra_data["attempt"] = attempt
    if provider_message_id:
        extra_data["provider_message_id"] = provider_message_id
    if duration_ms is not None:
        extra_data["duration_ms"] = duration_ms
        
    if extras:
        extra_data.update(extras)

    record_kwargs = {
        "extra": {
            "event_name": event_name,
            "extra_data": extra_data
        }
    }

    if nivel.upper() == "ERROR":
        logger.error(mensagem, **record_kwargs)
    elif nivel.upper() == "WARNING":
        logger.warning(mensagem, **record_kwargs)
    else:
        logger.info(mensagem, **record_kwargs)