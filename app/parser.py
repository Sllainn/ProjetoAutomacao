import re
import unicodedata
from datetime import datetime
from typing import Dict, Any
from app.schemas import HearingData

def normalizar_chave(texto: str) -> str:
    """Regra 171: Normaliza maiúsculas, espaços e acentos dos rótulos."""
    texto = texto.strip().upper()
    # Remove acentos substituindo caracteres especiais
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto) 
        if unicodedata.category(c) != 'Mn'
    )
    return texto

def limpar_texto(texto: str) -> str:
    """Remove espaços em branco no início e no fim do valor."""
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

    # Mapeamento de rótulos permitidos (substitui a cascata de if/elif)
    mapeamento_chaves = {
        "TIPO": "tipo",
        "PROCESSO": "process_number",
        "CLIENTE_ID": "client_external_id",
        "MODALIDADE": "mode",
        "LINK_CLIENTE": "public_link",
        "LOCAL_CLIENTE": "public_location",
        "TESTEMUNHAS": "witness_instruction",
        "OBS_CLIENTE": "public_note"
    }

    # Regra 171 e 172: Percorre as linhas e filtra apenas os campos públicos da Whitelist
    for linha in linhas:
        if ":" not in linha:
            continue
        
        chave_bruta, valor = linha.split(":", 1)
        chave_normalizada = normalizar_chave(chave_bruta)
        valor_limpo = limpar_texto(valor)

        if chave_normalizada in mapeamento_chaves and valor_limpo:
            campo_destino = mapeamento_chaves[chave_normalizada]
            
            # Força minúsculas apenas para regras internas de TIPO e MODALIDADE
            if chave_normalizada in ["TIPO", "MODALIDADE"]:
                valor_limpo = valor_limpo.lower()
                
            dados_extraidos[campo_destino] = valor_limpo
        # Nota: O campo OBS_INTERNA é ignorado nativamente por não estar no mapeamento_chaves.

    # --- Validações e Regras de Negócio (Regras 173, 174, 176) ---
    
    # Validação do Número do Processo (Regra 173 - Padrão CNJ básico)
    proc_num = dados_extraidos.get("process_number", "")
    padrao_cnj = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
    if not proc_num or not re.match(padrao_cnj, proc_num):
        erros.append(f"Número de processo ausente, inválido ou fora do padrão CNJ: '{proc_num}'")

    # Validação do ID do Cliente (Regra 173)
    if not dados_extraidos.get("client_external_id"):
        erros.append("O identificador do cliente (CLIENTE_ID) está ausente ou vazio.")

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
    elif modalidade not in ["online", "presencial", "hibrida"]:
        erros.append(f"Modalidade '{modalidade}' não reconhecida. Use online, presencial ou hibrida.")

    # Se houver erros, aplicamos a Regra 176 (Marcar como review/rejeitar ambiguidades)
    if erros:
        return {
            "status": "review_required",
            "errors": erros,
            "raw_data": dados_extraidos
        }

    # Validação final utilizando o Pydantic (HearingData)
    try:
        hearing_model = HearingData(**dados_extraidos)
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