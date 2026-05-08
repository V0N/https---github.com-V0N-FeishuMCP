import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(
        self,
        feishu_app_id: str,
        feishu_app_secret: str,
        feishu_encrypt_key: str,
        feishu_admin_user_id: str,
        feishu_verification_token: str = "",
        allowed_user_ids: set[str] = None,
        log_level: str = "INFO",
        port: int = 8000,
    ):
        self.FEISHU_APP_ID = feishu_app_id
        self.FEISHU_APP_SECRET = feishu_app_secret
        self.FEISHU_ENCRYPT_KEY = feishu_encrypt_key
        self.FEISHU_ADMIN_USER_ID = feishu_admin_user_id
        self.FEISHU_VERIFICATION_TOKEN = feishu_verification_token
        self.ALLOWED_USER_IDS = allowed_user_ids if allowed_user_ids is not None else set()
        self.LOG_LEVEL = log_level
        self.PORT = port


def load_settings(env: dict = None) -> Settings:
    source = env if env is not None else os.environ

    def require(key: str) -> str:
        val = source.get(key)
        if not val:
            raise ValueError(f"缺少必填环境变量: {key}")
        return val

    feishu_app_id = require("FEISHU_APP_ID")
    feishu_app_secret = require("FEISHU_APP_SECRET")
    feishu_encrypt_key = require("FEISHU_ENCRYPT_KEY")
    feishu_admin_user_id = require("FEISHU_ADMIN_USER_ID")

    feishu_verification_token = source.get("FEISHU_VERIFICATION_TOKEN", "")

    raw_allowed = source.get("ALLOWED_USER_IDS", "")
    allowed_user_ids: set[str] = (
        {uid.strip() for uid in raw_allowed.split(",") if uid.strip()}
        if raw_allowed
        else set()
    )

    log_level = source.get("LOG_LEVEL", "INFO")

    raw_port = source.get("PORT", "8000")
    port = int(raw_port)

    return Settings(
        feishu_app_id=feishu_app_id,
        feishu_app_secret=feishu_app_secret,
        feishu_encrypt_key=feishu_encrypt_key,
        feishu_admin_user_id=feishu_admin_user_id,
        feishu_verification_token=feishu_verification_token,
        allowed_user_ids=allowed_user_ids,
        log_level=log_level,
        port=port,
    )


try:
    settings = load_settings()
except ValueError:
    settings = None
