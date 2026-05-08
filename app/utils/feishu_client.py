import asyncio
import time

import httpx

from app.config.settings import settings

FEISHU_BASE_URL = "https://open.feishu.cn/open-apis"


class FeishuAPIError(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg


class FeishuClient:
    def __init__(self, app_id: str = None, app_secret: str = None):
        self._app_id = app_id or (settings.FEISHU_APP_ID if settings else "")
        self._app_secret = app_secret or (settings.FEISHU_APP_SECRET if settings else "")
        self._token: str | None = None
        self._token_expire_at: float = 0.0
        self._lock = asyncio.Lock()
        self._client = httpx.AsyncClient()

    async def get_tenant_access_token(self) -> str:
        async with self._lock:
            now = time.time()
            if self._token and (self._token_expire_at - now) > 600:
                return self._token

            resp = await self._client.post(
                f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal",
                json={"app_id": self._app_id, "app_secret": self._app_secret},
            )
            data = resp.json()
            if data.get("code", -1) != 0:
                raise FeishuAPIError(data.get("code", -1), data.get("msg", ""))

            self._token = data["tenant_access_token"]
            self._token_expire_at = now + data["expire"]
            return self._token

    async def request(self, method: str, path: str, **kwargs) -> dict:
        token = await self.get_tenant_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        resp = await self._client.request(
            method,
            f"{FEISHU_BASE_URL}{path}",
            headers=headers,
            **kwargs,
        )
        data = resp.json()
        if data.get("code", 0) != 0:
            raise FeishuAPIError(data["code"], data.get("msg", ""))
        return data


feishu_client = FeishuClient()
