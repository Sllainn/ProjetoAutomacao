import httpx
from typing import Protocol, List
from dataclasses import dataclass

@dataclass(frozen=True)
class SendResult:
    message_id: str
    status: str

class WhatsAppClient(Protocol):
    async def send_template(
        self,
        *,
        phone_e164: str,
        template_name: str,
        language: str,
        parameters: List[str],
        idempotency_key: str,
    ) -> SendResult:
        ...

class OfficialWhatsAppClient:
    def __init__(self, api_url: str, token: str, timeout: float = 15.0):
        self.api_url = api_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    async def send_template(
        self,
        *,
        phone_e164: str,
        template_name: str,
        language: str,
        parameters: List[str],
        idempotency_key: str,
    ) -> SendResult:
        """
        Envia um template aprovado via API Oficial do WhatsApp (WABA),
        respeitando a idempotência e os parâmetros especificados.
        """
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": phone_e164,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": value} for value in parameters
                        ]
                    }
                ]
            }
        }

        # O cabeçalho de idempotency_key pode ser incluído se suportado pela versão da graph api utilizada
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.api_url, json=payload, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            # Extração padrão do ID de mensagem retornado pela API da Meta
            messages = data.get("messages", [{}])
            message_id = messages[0].get("id", "desconhecido")

            return SendResult(message_id=message_id, status="sent")