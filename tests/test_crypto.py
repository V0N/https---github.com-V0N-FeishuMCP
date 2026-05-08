import base64
import hashlib
import json

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from app.utils.crypto import DecryptError, decrypt_feishu_event


def encrypt_feishu_event(payload: dict, encrypt_key: str) -> str:
    key = hashlib.sha256(encrypt_key.encode()).digest()[:32]
    plaintext = json.dumps(payload).encode("utf-8")
    padded = pad(plaintext, AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.IV
    encrypted = cipher.encrypt(padded)
    return base64.b64encode(iv + encrypted).decode("utf-8")


def test_decrypt_correct():
    encrypt_key = "test_secret_key"
    original = {"event_type": "attendance", "user_id": "u001"}
    encrypt_str = encrypt_feishu_event(original, encrypt_key)
    result = decrypt_feishu_event(encrypt_str, encrypt_key)
    assert result == original


def test_decrypt_wrong_key_raises_decrypt_error():
    encrypt_key = "correct_key"
    wrong_key = "wrong_key_abc"
    payload = {"foo": "bar"}
    encrypt_str = encrypt_feishu_event(payload, encrypt_key)
    with pytest.raises(DecryptError):
        decrypt_feishu_event(encrypt_str, wrong_key)


def test_decrypt_invalid_base64_raises_decrypt_error():
    with pytest.raises(DecryptError):
        decrypt_feishu_event("!!!not_valid_base64!!!", "any_key")


def test_decrypt_invalid_json_raises_decrypt_error():
    encrypt_key = "test_key"
    key = hashlib.sha256(encrypt_key.encode()).digest()[:32]
    plaintext = b"this is not json at all"
    padded = pad(plaintext, AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.IV
    encrypted = cipher.encrypt(padded)
    encrypt_str = base64.b64encode(iv + encrypted).decode("utf-8")
    with pytest.raises(DecryptError):
        decrypt_feishu_event(encrypt_str, encrypt_key)


def test_decrypt_challenge_field():
    encrypt_key = "challenge_key_123"
    payload = {"challenge": "ajls384jgns", "token": "some_token", "type": "url_verification"}
    encrypt_str = encrypt_feishu_event(payload, encrypt_key)
    result = decrypt_feishu_event(encrypt_str, encrypt_key)
    assert "challenge" in result
    assert result["challenge"] == "ajls384jgns"
