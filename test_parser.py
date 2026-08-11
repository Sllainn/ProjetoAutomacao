import pytest
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, HttpUrl, ValidationError
from typing import Optional
from app.parser import parsear_descricao_evento

# Simulando o seu HearingData caso precise rodar o teste isolado
class HearingData(BaseModel):
    google_event_id: str
    starts_at: datetime
    timezone: str
    tipo: Optional[str] = None
    process_number: str
    client_external_id: str
    mode: str
    public_link: Optional[HttpUrl] = None
    public_location: Optional[str] = None
    witness_instruction: Optional[str] = None
    public_note: Optional[str] = None

# Substitua 'seu_modulo' pelo nome do arquivo onde está a função parsear_descricao_evento
from app.parser import parsear_descricao_evento

# --- FIXTURES FICTÍCIAS ---
FUSO_SP = "America/Sao_Paulo"
DATA_TESTE = datetime(2026, 8, 15, 14, 30, tzinfo=timezone(timedelta(hours=-3)))
EVENT_ID = "evento_ficticio_123"

DESC_ONLINE = """TIPO: AUDIENCIA
PROCESSO: 0000000-00.0000.0.00.0000
CLIENTE_ID: CRM-TESTE-001
MODALIDADE: ONLINE
LINK_CLIENTE: https://meet.example.test/sala-ficticia
OBS_CLIENTE: Entrar 10 min antes"""

DESC_PRESENCIAL = """TIPO: AUDIENCIA
PROCESSO: 1111111-11.1111.1.11.1111
CLIENTE_ID: CRM-TESTE-002
MODALIDADE: PRESENCIAL
LOCAL_CLIENTE: Fórum Central, Sala 404"""

DESC_HIBRIDA = """TIPO: AUDIENCIA
PROCESSO: 2222222-22.2222.2.22.2222
CLIENTE_ID: CRM-TESTE-003
MODALIDADE: HIBRIDA
LINK_CLIENTE: https://meet.example.test/hibrida
LOCAL_CLIENTE: Fórum de Testes, Sala 1"""

DESC_OBS_INTERNA = """TIPO: AUDIENCIA
PROCESSO: 0000000-00.0000.0.00.0000
CLIENTE_ID: CRM-TESTE-004
MODALIDADE: ONLINE
LINK_CLIENTE: https://meet.example.test/sala-ficticia
OBS_INTERNA: O cliente não tem acordo. Focar na tese subsidiária."""

# --- TESTES ---

def test_parsear_descricao_vazia():
    """Testa se o parser rejeita uma descrição vazia."""
    resultado = parsear_descricao_evento(EVENT_ID, "", DATA_TESTE, FUSO_SP)
    assert resultado["status"] == "error"
    assert "vazia" in resultado["errors"][0]

@pytest.mark.parametrize("descricao, modo_esperado", [
    (DESC_ONLINE, "online"),
    (DESC_PRESENCIAL, "presencial"),
    (DESC_HIBRIDA, "hibrida")
])
def test_parsear_modalidades_validas(descricao, modo_esperado):
    """Testa se as modalidades online, presencial e híbrida são processadas com sucesso."""
    resultado = parsear_descricao_evento(EVENT_ID, descricao, DATA_TESTE, FUSO_SP)
    assert resultado["status"] == "success"
    dados = resultado["data"]
    assert dados.mode == modo_esperado
    assert dados.starts_at == DATA_TESTE
    assert dados.timezone == FUSO_SP

def test_falta_campo_obrigatorio_online():
    """Testa se a modalidade online falha sem o LINK_CLIENTE."""
    desc_sem_link = """TIPO: AUDIENCIA
PROCESSO: 0000000-00.0000.0.00.0000
MODALIDADE: ONLINE"""
    resultado = parsear_descricao_evento(EVENT_ID, desc_sem_link, DATA_TESTE, FUSO_SP)
    assert resultado["status"] == "review_required"
    assert any("exige obrigatoriamente um LINK_CLIENTE" in erro for erro in resultado["errors"])

def test_obs_interna_ignorada():
    """Testa e confirma explicitamente que a OBS_INTERNA nunca aparece no modelo público."""
    resultado = parsear_descricao_evento(EVENT_ID, DESC_OBS_INTERNA, DATA_TESTE, FUSO_SP)
    assert resultado["status"] == "success"
    
    # Verifica os dados brutos e o modelo final
    dados_dict = resultado["data"].model_dump()
    chaves_modelo = dados_dict.keys()
    
    # Assertivas de segurança rigorosas
    assert "obs_interna" not in chaves_modelo
    assert "OBS_INTERNA" not in chaves_modelo
    # Garante que o texto restrito não vazou para o campo de nota pública
    assert dados_dict.get("public_note") != "O cliente não tem acordo. Focar na tese subsidiária."

def test_url_invalida_rejeitada():
    """Testa se uma URL malformada é barrada pelo contrato do Pydantic."""
    desc_url_ruim = """TIPO: AUDIENCIA
PROCESSO: 0000000-00.0000.0.00.0000
CLIENTE_ID: CRM-TESTE-005
MODALIDADE: ONLINE
LINK_CLIENTE: htp://link-quebrado"""
    
    resultado = parsear_descricao_evento(EVENT_ID, desc_url_ruim, DATA_TESTE, FUSO_SP)
    assert resultado["status"] == "review_required"
    assert any("Erro de validação no contrato Pydantic" in erro for erro in resultado["errors"])