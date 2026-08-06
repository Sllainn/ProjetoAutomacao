from typing import Optional
from app.crm import CRMClient, FakeCRMClient, CRMContact

async def resolver_contato_audiencia(
    client_external_id: str, 
    crm_client: CRMClient = FakeCRMClient()
) -> dict:
    """
    Executa o fluxo de busca de contato no CRM seguindo as regras:
    - Recebe o identificador explícito (Regra 179)
    - Consulta o CRM (Regra 181)
    - Valida se o contato está ativo e se o telefone está em formato E.164 (Regra 182)
    - Retorna erro/review se não encontrar ou se houver inconsistência (Regra 184)
    - Não altera nem cria dados automaticamente (Regra 185)
    """
    if not client_external_id:
        return {
            "status": "review_required",
            "error": "Identificador externo do cliente ausente no evento."
        }

    try:
        # Consulta o CRM (pode ser o Fake ou o cliente real futuramente)
        contato = await crm_client.get_contact(client_external_id)

        if not contato:
            return {
                "status": "review_required",
                "error": f"Nenhum contato encontrado no CRM para o ID: {client_external_id} (Regra 184)."
            }

        # Validação do contato ativo e do formato de telefone E.164 (Regra 182)
        if not contato.active:
            return {
                "status": "review_required",
                "error": f"O contato {client_external_id} está inativo no CRM."
            }

        # Validação básica de formato E.164 (ex: deve começar com '+' e ter apenas números após)
        if not contato.phone_e164 or not contato.phone_e164.startswith("+"):
            return {
                "status": "review_required",
                "error": f"O telefone do contato {client_external_id} não está no formato E.164 válido: '{contato.phone_e164}'."
            }

        return {
            "status": "success",
            "contact": contato
        }

    except Exception as e:
        return {
            "status": "review_required",
            "error": f"Erro de comunicação ao consultar o CRM: {str(e)}"
        }