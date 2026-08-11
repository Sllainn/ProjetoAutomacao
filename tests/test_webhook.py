import hmac
import hashlib
import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.webhook import WEBHOOK_VERIFY_TOKEN, META_APP_SECRET

client = TestClient(app)

def gerar_assinatura_valida(payload: bytes, secret: str) -> str:
    """Gera um cabeçalho X-Hub-Signature-256 válido para os testes."""
    mac = hmac.new(
        secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256
    )
    return f"sha256={mac.hexdigest()}"


def test_verificacao_webhook_sucesso():
    """Testa a validação GET (challenge) exigida pela Meta."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": WEBHOOK_VERIFY_TOKEN,
            "hub.challenge": "123456789"
        }
    )
    assert response.status_code == 200
    assert response.json() == 123456789


def test_verificacao_webhook_token_invalido():
    """Testa a recusa do GET caso o token de verificação esteja errado."""
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "token_errado",
            "hub.challenge": "123456789"
        }
    )
    assert response.status_code == 403


def test_webhook_post_assinatura_invalida():
    """Testa a rejeição (401) de um POST com assinatura ausente ou incorreta."""
    payload = json.dumps({"object": "whatsapp_business_account"}).encode("utf-8")
    
    response = client.post(
        "/webhook",
        data=payload,
        headers={"X-Hub-Signature-256": "sha256=assinatura_falsa"}
    )
    assert response.status_code == 401


def test_webhook_post_status_sucesso():
    """Testa o processamento bem-sucedido de um evento de status da Meta."""
    payload_dict = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid_teste_12345",
                                    "status": "delivered",
                                    "timestamp": "1710000000"
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    
    payload_bytes = json.dumps(payload_dict).encode("utf-8")
    signature = gerar_assinatura_valida(payload_bytes, META_APP_SECRET)

    response = client.post(
        "/webhook",
        data=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"status": "success"}