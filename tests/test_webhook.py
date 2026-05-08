import base64
import hashlib
import json
from unittest.mock import AsyncMock, patch

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from fastapi.testclient import TestClient

TEST_ENCRYPT_KEY = "test_encrypt_key_for_webhook_test"


def encrypt_feishu_event(payload: dict, encrypt_key: str) -> str:
    key = hashlib.sha256(encrypt_key.encode()).digest()[:32]
    plaintext = json.dumps(payload).encode("utf-8")
    padded = pad(plaintext, AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.IV
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(iv + encrypted).decode("utf-8")


def make_encrypted_body(payload: dict, encrypt_key: str = TEST_ENCRYPT_KEY) -> dict:
    return {"encrypt": encrypt_feishu_event(payload, encrypt_key)}


@pytest.fixture
def client():
    import app.config.settings as settings_mod
    import app.api.webhook as webhook_mod
    from app.main import app

    test_settings = settings_mod.load_settings({
        "FEISHU_APP_ID": "test_app_id",
        "FEISHU_APP_SECRET": "test_app_secret",
        "FEISHU_ENCRYPT_KEY": TEST_ENCRYPT_KEY,
        "FEISHU_ADMIN_USER_ID": "test_admin_user",
    })

    with patch.object(settings_mod, "settings", test_settings), \
         patch.object(webhook_mod, "settings", test_settings):
        yield TestClient(app)


def test_url_verification(client):
    challenge_value = "test_challenge_abc123"
    payload = {
        "challenge": challenge_value,
        "token": "some_token",
        "type": "url_verification",
    }
    body = make_encrypted_body(payload)
    response = client.post("/webhook/lark/event", json=body)
    assert response.status_code == 200
    assert response.json() == {"challenge": challenge_value}


def test_message_event_returns_200(client):
    payload = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "event_id": "evt_001",
        },
        "event": {
            "message": {
                "message_id": "msg_001",
                "message_type": "text",
                "content": '{"text": "hello"}',
            }
        },
    }
    body = make_encrypted_body(payload)

    with patch("app.api.webhook.process_message_event", new_callable=AsyncMock) as mock_process:
        with patch("app.api.webhook._run_process_message_event") as mock_run:
            response = client.post("/webhook/lark/event", json=body)
            assert response.status_code == 200
            assert response.json() == {}
            mock_run.assert_called_once_with(payload)


def test_decrypt_failure_returns_400(client):
    body = {"encrypt": "this_is_not_valid_ciphertext!!!"}
    response = client.post("/webhook/lark/event", json=body)
    assert response.status_code == 400
    assert response.json() == {"code": 400, "msg": "decrypt failed"}


def test_non_message_event_ignored(client):
    payload = {
        "schema": "2.0",
        "header": {
            "event_type": "approval.instance.status_changed",
            "event_id": "evt_002",
        },
        "event": {
            "instance_code": "appr_001",
        },
    }
    body = make_encrypted_body(payload)

    with patch("app.api.webhook.process_message_event", new_callable=AsyncMock) as mock_process:
        response = client.post("/webhook/lark/event", json=body)
        assert response.status_code == 200
        mock_process.assert_not_called()
