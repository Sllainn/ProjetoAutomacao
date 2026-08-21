from dataclasses import dataclass
from typing import Protocol

import httpx


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
        parameters: list[str],
        idempotency_key: str,
    ) -> SendResult:
        ...

class OfficialWhatsAppClient:
    def __init__(self, api_url: str, token: str, timeout: float = 15.0):
        self.api_url = api_url.rstrip("/")
        
        # Limpeza do token
        clean_token = token.strip().strip("'").strip('"')
        if clean_token.lower().startswith("bearer "):
            clean_token = clean_token[7:].strip()
            
        self.token = clean_token
        self.timeout = timeout

    async def send_template(
        self,
        *,
        phone_e164: str,
        template_name: str,
        language: str,
        parameters: list[str],
        idempotency_key: str,
    ) -> SendResult:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        template_obj = {
            "name": template_name,
            "language": {"code": language}
        }

        # Anexa components apenas se houver parâmetros
        if parameters:
            template_obj["components"] = [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": str(value)} for value in parameters
                    ]
                }
            ]

        payload = {
            "messaging_product": "whatsapp",
            "to": str(phone_e164).replace("+", "").strip(),
            "type": "template",
            "template": template_obj
        }

        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        # Bloco de envio e captura de logs detalhados
        try:
            print(f" PAYLOAD ENVIADO PARA META: {payload}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                
                if response.is_error:
                    print(f"RESPOSTA META [{response.status_code}]: {response.text}")
                
                response.raise_for_status()
                
                data = response.json()
                messages = data.get("messages", [{}])
                message_id = messages[0].get("id", "desconhecido")

                return SendResult(message_id=message_id, status="sent")
                
        except httpx.HTTPStatusError as e:
            print(f"HTTPStatusError na API do WhatsApp: {e.response.text}")
            raise 
        except Exception as e:
            print(f"Erro de conexão no cliente do WhatsApp: {e!s}")
            raise 