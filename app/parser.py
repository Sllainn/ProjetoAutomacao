import re
from datetime import datetime
from typing import Dict, Any, Optional
import app.schemas

def limpar_texto(texto: str) -> str:
    """Regra 171: Normaliza maiúsculas, espaços e acentos básicos se necessário."""
    return texto.strip()

def parsear_descricao_evento(event_id: str, descricao: str, start_dt: datetime, timezone_str: str) -> Dict[str, Any]:
    """
    Realiza o parse da descrição humana do evento do Google Calendar 
    e valida contra o contrato de dados HearingData.
    """
    if not descricao:
        return {
            "status": "error",
            "errors": ["A descrição do evento está vazia. Impossível realizar o parse."]
        }

    # Dicionário para armazenar os campos extraídos
    dados_extraidos = {
        "google_event_id": event_id,
        "starts_at": start_dt,
        "timezone": timezone_str
    }
    
    erros = []
    linhas = descricao.splitlines()

    # Mapeamento de rótulos permitidos (Regra 171)
    for linha in linhas:
        if ":" not in linha:
            continue
        
        chave, valor = linha.split(":", 1)
        chave = chave.strip().upper()
        valor = limpar_texto(valor)

        if chave == "TIPO":
            dados_extraidos["tipo"] = valor.lower()
        elif chave == "PROCESSO":
            dados_extraidos["process_number"] = valor
        elif chave == "CLIENTE_ID":
            dados_extraidos["client_external_id"] = valor
        elif chave == "MODALIDADE":
            dados_extraidos["mode"] = valor.lower()
        elif chave == "LINK_CLIENTE":
            dados_extraidos["public_link"] = valor if valor else None
        elif chave == "LOCAL_CLIENTE":
            dados_extraidos["public_location"] = valor if valor else None
        elif chave == "TESTEMUNHAS":
            dados_extraidos["witness_instruction"] = valor if valor else None
        elif chave == "OBS_CLIENTE":
            dados_extraidos["public_note"] = valor if valor else None
        # Nota: O campo OBS_INTERNA é ignorado propositalmente (Regra 172)

    # --- Validações e Regras de Negócio (Regras 173, 174, 176) ---
    
    # Validação do Número do Processo (Regra 173 - Padrão CNJ básico 0000000-00.0000.0.00.0000)
    proc_num = dados_extraidos.get("process_number", "")
    padrao_cnj = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
    if not re.match(padrao_cnj, proc_num):
        erros.append(f"Número de processo inválido ou fora do padrão CNJ: '{proc_num}'")

    # Validação de Modalidade e Links/Endereços obrigatórios (Regra 174)
    modalidade = dados_extraidos.get("mode")
    link = dados_extraidos.get("public_link")
    local = dados_extraidos.get("public_location")

    if modalidade == "online" and not link:
        erros.append("Modalidade 'online' exige obrigatoriamente um LINK_CLIENTE válido.")
    elif modalidade == "presencial" and not local:
        erros.append("Modalidade 'presencial' exige obrigatoriamente um LOCAL_CLIENTE preenchido.")
    elif modalidade == "hibrida" and (not link or not local):
        erros.append("Modalidade 'hibrida' exige tanto LINK_CLIENTE quanto LOCAL_CLIENTE.")

    # Se houver erros, aplicamos a Regra 176 (Marcar como review/rejeitar ambiguidades)
    if erros:
        return {
            "status": "review_required",
            "errors": erros,
            "raw_data": dados_extraidos
        }

    # Validação final utilizando o Pydantic (HearingData)
    try:
        hearing_model = app.schemas.HearingData(**dados_extraidos)
        return {
            "status": "success",
            "data": hearing_model
        }
    except Exception as e:
        return {
            "status": "review_required",
            "errors": [f"Erro de validação no contrato Pydantic: {str(e)}"],
            "raw_data": dados_extraidos
        }