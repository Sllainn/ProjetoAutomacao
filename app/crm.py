from dataclasses import dataclass
from typing import Protocol, Optional

@dataclass(frozen=True)
class CRMContact:
    external_id: str
    display_name: str
    phone_e164: str
    active: bool

class CRMClient(Protocol):
    async def get_contact(
        self,
        client_external_id: str,
    ) -> CRMContact | None:
        ...

# --- Mock para desenvolver sem bloquear o restante (Regra de Ouro) ---
class FakeCRMClient:
    async def get_contact(self, client_external_id: str) -> Optional[CRMContact]:
        if client_external_id == "CRM-TESTE-001":
            return CRMContact(
                external_id=client_external_id,
                display_name="Cliente Teste",
                phone_e164="+5551999990001",
                active=True
            )
        return None