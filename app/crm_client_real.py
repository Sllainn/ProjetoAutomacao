import httpx
from typing import Optional
from app.crm import CRMContact

class RealCRMClient:
    def __init__(self, base_url: str, api_token: str, timeout: float = 5.0):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

    async def get_contact(self, client_external_id: str) -> Optional[CRMContact]:
        """
        Consulta a API real do CRM utilizando httpx.AsyncClient com tratamento de erros
        e logs seguros (sem expor tokens ou dados sensíveis).
        """
        url = f"{self.base_url}/contacts/{client_external_id}"
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(url, headers=headers)
                
                # Tratamento de Erros conforme o Troubleshooting
                if response.status_code == 404:
                    print(f"ℹ️ CRM: Contato externo '{client_external_id}' não encontrado.")
                    return None
                
                if response.status_code in (401, 403):
                    print("❌ CRM Erro 401/403: Falha de autenticação ou permissão (verifique o token de ambiente).")
                    raise PermissionError("Erro de autenticação ou escopo inválido no CRM.")
                
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "desconhecido")
                    print(f"⚠️ CRM Erro 429: Limite da API atingido (Rate Limit). Tente novamente após: {retry_after}s.")
                    raise ConnectionError("Limite de requisições da API do CRM excedido.")
                
                if response.status_code >= 500:
                    print(f"❌ CRM Erro {response.status_code}: Instabilidade temporária no servidor do fornecedor.")
                    raise ConnectionError("Erro interno no servidor do CRM.")

                response.raise_for_status()
                data = response.json()

                # Mapeia a resposta da API para a dataclass interna CRMContact
                return CRMContact(
                    external_id=data.get("external_id"),
                    display_name=data.get("display_name"),
                    phone_e164=data.get("phone_e164"),
                    active=data.get("active", True)
                )

            except httpx.TimeoutException:
                print(f"⏳ CRM Timeout: A requisição para o ID '{client_external_id}' excedeu o tempo limite.")
                raise
            except httpx.RequestError as e:
                # Log seguro: evita expor dados confidenciais na stack trace
                print(f"❌ CRM Erro de Conexão ao buscar contato.")
                raise e