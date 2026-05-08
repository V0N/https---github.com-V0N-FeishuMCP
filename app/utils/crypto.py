import base64
import hashlib
import json

from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad


class DecryptError(Exception):
    pass


def decrypt_feishu_event(encrypt_str: str, encrypt_key: str) -> dict:
    try:
        key = hashlib.sha256(encrypt_key.encode()).digest()[:32]
        data = base64.b64decode(encrypt_str)
        iv = data[:16]
        cipher_text = data[16:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        decrypted = unpad(cipher.decrypt(cipher_text), AES.block_size)
        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        raise DecryptError(f"解密失败: {e}") from e
