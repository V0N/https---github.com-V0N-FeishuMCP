import time

import pytest
import respx
from httpx import Response

from app.utils.feishu_client import FEISHU_BASE_URL, FeishuAPIError, FeishuClient

TOKEN_URL = f"{FEISHU_BASE_URL}/auth/v3/tenant_access_token/internal"


def make_client() -> FeishuClient:
    return FeishuClient(app_id="test_app_id", app_secret="test_app_secret")


def token_response(token: str = "test_token", expire: int = 7200) -> Response:
    return Response(
        200,
        json={"code": 0, "msg": "ok", "tenant_access_token": token, "expire": expire},
    )


@respx.mock
async def test_get_token_first_call():
    route = respx.post(TOKEN_URL).mock(return_value=token_response("first_token"))
    client = make_client()
    token = await client.get_tenant_access_token()
    assert token == "first_token"
    assert route.called


@respx.mock
async def test_get_token_cached():
    route = respx.post(TOKEN_URL).mock(return_value=token_response("cached_token"))
    client = make_client()
    token1 = await client.get_tenant_access_token()
    token2 = await client.get_tenant_access_token()
    assert token1 == token2 == "cached_token"
    assert route.call_count == 1


@respx.mock
async def test_get_token_refresh_near_expiry():
    route = respx.post(TOKEN_URL).mock(
        side_effect=[
            token_response("old_token"),
            token_response("new_token"),
        ]
    )
    client = make_client()
    await client.get_tenant_access_token()
    client._token_expire_at = time.time() + 300
    token = await client.get_tenant_access_token()
    assert token == "new_token"
    assert route.call_count == 2


@respx.mock
async def test_request_adds_auth_header():
    respx.post(TOKEN_URL).mock(return_value=token_response("auth_token"))
    api_route = respx.get(f"{FEISHU_BASE_URL}/some/api").mock(
        return_value=Response(200, json={"code": 0, "msg": "ok", "data": {}})
    )
    client = make_client()
    await client.request("GET", "/some/api")
    assert api_route.called
    request = api_route.calls.last.request
    assert request.headers["Authorization"] == "Bearer auth_token"


@respx.mock
async def test_request_raises_feishu_api_error():
    respx.post(TOKEN_URL).mock(return_value=token_response())
    respx.get(f"{FEISHU_BASE_URL}/bad/api").mock(
        return_value=Response(200, json={"code": 99991663, "msg": "invalid token"})
    )
    client = make_client()
    with pytest.raises(FeishuAPIError) as exc_info:
        await client.request("GET", "/bad/api")
    assert exc_info.value.code == 99991663
    assert exc_info.value.msg == "invalid token"
