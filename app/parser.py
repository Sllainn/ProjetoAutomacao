import re
import html
import unicodedata
from datetime import datetime
from typing import Dict, Any
from app.schemas import HearingData

def normalizar_chave(texto: str) -> str:
    # Faz o tratamento de letras maiúsculas, espaços e acentos dos rótulos.
    texto = texto.strip().upper()
    texto = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto

def limpar_html(texto: str) -> str:
    # Converte tags HTML comuns em quebras de linha e remove marcações restantes.
    if not texto:
        return ""
    
    # Decodifica entidades HTML como &nbsp;, &amp;, &lt;, etc.
    texto = html.unescape(texto)
    texto = texto.replace('\xa0', ' ')

    # Converte tags de quebra/bloco para quebras de linha reais
    texto = re.sub(r'(?i)<br\s*/?>', '\n', texto)
    texto = re.sub(r'(?i)</?(div|p|tr|li)[^>]*>', '\n', texto)

    # Remove quaisquer outras tags HTML
    texto = re.sub(r'<[^<]+?>', '', texto)
    return texto

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

    dados_extraidos = {
        "google_event_id": event_id,
        "starts_at": start_dt,
        "timezone": timezone_str
    }

    erros = []
    texto_puro = limpar_html(descricao)
    linhas = texto_puro.splitlines()

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

    for linha in linhas:
        linha_limpa = linha.strip()
        if ":" not in linha_limpa:
            continue

        chave_bruta, valor = linha_limpa.split(":", 1)
        chave_normalizada = normalizar_chave(chave_bruta)
        valor_limpo = valor.strip()

        if chave_normalizada in mapeamento_chaves and valor_limpo:
            campo_destino = mapeamento_chaves[chave_normalizada]

            if chave_normalizada in ["TIPO", "MODALIDADE"]:
                valor_limpo = valor_limpo.lower()

            dados_extraidos[campo_destino] = valor_limpo

    # Validação do Número do Processo
    proc_num = dados_extraidos.get("process_number", "")
    padrao_cnj = r"^\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}$"
    if not proc_num or not re.match(padrao_cnj, proc_num):
        erros.append(f"Número de processo ausente, inválido ou fora do padrão CNJ: '{proc_num}'")

    # Validação do ID do Cliente
    cliente_id = dados_extraidos.get("client_external_id", "")

    # Remove eventuais caracteres não numéricos do telefone
    cliente_id_limpo = re.sub(r"\D", "", cliente_id)
    
    if not cliente_id_limpo:
        erros.append("O identificador do cliente (CLIENTE_ID) está ausente ou vazio.")
    else:
        dados_extraidos["client_external_id"] = cliente_id_limpo

    # Validação de Modalidade e Links/Endereços
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

    if erros:
        return {
            "status": "review_required",
            "errors": erros,
            "raw_data": dados_extraidos
        }

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
