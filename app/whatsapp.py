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

        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                
                # Se a Meta retornar erro (ex: 400, 401, 403, 500), capturamos o corpo da resposta para debug
                if response.is_error:
                    print(f"❌ ERRO HTTP DA META [{response.status_code}]: {response.text}")
                
                response.raise_for_status()
                
                data = response.json()
                messages = data.get("messages", [{}])
                message_id = messages[0].get("id", "desconhecido")

                return SendResult(message_id=message_id, status="sent")
                
        except httpx.HTTPStatusError as e:
            print(f"❌ HTTPStatusError na API do WhatsApp: {e.response.text}")
            raise e
        except Exception as e:
            print(f"❌ Erro de conexão/execução no cliente do WhatsApp: {str(e)}")
            raise e