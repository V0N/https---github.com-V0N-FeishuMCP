import base64
import hashlib
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from fastapi.testclient import TestClient

ENCRYPT_KEY = "test_encrypt_key_integration"


def make_env():
    return {
        "FEISHU_APP_ID": "test_app_id",
        "FEISHU_APP_SECRET": "test_app_secret",
        "FEISHU_ENCRYPT_KEY": ENCRYPT_KEY,
        "FEISHU_ADMIN_USER_ID": "u_admin",
        "ALLOWED_USER_IDS": "ou_admin",
    }


def encrypt_event(payload: dict) -> dict:
    key = hashlib.sha256(ENCRYPT_KEY.encode()).digest()[:32]
    plaintext = json.dumps(payload).encode("utf-8")
    padded = pad(plaintext, AES.block_size)
    cipher = AES.new(key, AES.MODE_CBC)
    iv = cipher.IV
    encrypted = cipher.encrypt(padded)
    encrypt_str = base64.b64encode(iv + encrypted).decode("utf-8")
    return {"encrypt": encrypt_str}


def make_message_event(open_id: str, text: str) -> dict:
    return {
        "schema": "2.0",
        "header": {"event_type": "im.message.receive_v1"},
        "event": {
            "sender": {"sender_id": {"open_id": open_id}},
            "message": {
                "message_type": "text",
                "content": json.dumps({"text": text}),
            },
        },
    }


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    for k, v in make_env().items():
        monkeypatch.setenv(k, v)


@pytest.fixture
def client():
    mock_dir_client = MagicMock()
    mock_att_client = MagicMock()
    mock_msg_client = MagicMock()

    mock_dir_client.request = AsyncMock(return_value={"data": {"items": [], "has_more": False}})
    mock_att_client.request = AsyncMock(return_value={"data": {}})
    mock_msg_client.request = AsyncMock(return_value={})

    with patch("app.service.directory_service.feishu_client", mock_dir_client), \
         patch("app.service.attendance_service.feishu_client", mock_att_client), \
         patch("app.service.message_service.feishu_client", mock_msg_client):

        import importlib
        import app.config.settings as settings_mod
        import app.service.directory_service as dir_mod
        import app.service.attendance_service as att_mod
        import app.service.message_service as msg_mod
        import app.service.message_handler as handler_mod

        importlib.reload(settings_mod)

        dir_mod.directory_service = dir_mod.DirectoryService(mock_dir_client)
        att_mod.attendance_service = att_mod.AttendanceService(
            mock_att_client,
            os.environ.get("FEISHU_ADMIN_USER_ID", "u_admin"),
        )
        msg_mod.message_service = msg_mod.MessageService(mock_msg_client)
        handler_mod.message_handler = None

        from app.service.session_service import SessionService

        async def fake_startup():
            from app.service.message_handler import MessageHandler
            handler_mod.message_handler = MessageHandler(
                directory_service=dir_mod.directory_service,
                attendance_service=att_mod.attendance_service,
                message_service=msg_mod.message_service,
                session_service=SessionService(),
            )

        import app.main as main_mod
        importlib.reload(main_mod)

        with patch.object(main_mod.app.router, "on_startup", [fake_startup]):
            with TestClient(main_mod.app) as c:
                c._dir_service = dir_mod.directory_service
                c._att_service = att_mod.attendance_service
                c._msg_service = msg_mod.message_service
                c._handler_mod = handler_mod
                yield c


def test_url_verification(client):
    body = encrypt_event({"challenge": "abc123"})
    response = client.post("/webhook/lark/event", json=body)
    assert response.status_code == 200
    assert response.json() == {"challenge": "abc123"}


def test_decrypt_failure(client):
    body = {"encrypt": "invalid_base64!!!"}
    response = client.post("/webhook/lark/event", json=body)
    assert response.status_code == 400
    assert response.json()["code"] == 400


def test_single_user_query(client):
    handler_mod = client._handler_mod
    mock_handle = AsyncMock()
    original_handler = handler_mod.message_handler

    handler_mod.message_handler = MagicMock()
    handler_mod.message_handler.handle_message = mock_handle

    try:
        payload = make_message_event("ou_user1", "查 张三 上月")
        body = encrypt_event(payload)

        with patch("app.api.webhook._run_process_message_event") as mock_run:
            response = client.post("/webhook/lark/event", json=body)
            assert response.status_code == 200
            mock_run.assert_called_once()
    finally:
        handler_mod.message_handler = original_handler


def test_query_self_flow(client):
    handler_mod = client._handler_mod

    captured_event = {}

    async def capture_handle(event_data):
        captured_event.update(event_data)

    handler_mod.message_handler = MagicMock()
    handler_mod.message_handler.handle_message = AsyncMock(side_effect=capture_handle)

    payload = make_message_event("ou_self_user", "查我 上月")
    body = encrypt_event(payload)

    with patch("app.api.webhook._run_process_message_event") as mock_run:
        response = client.post("/webhook/lark/event", json=body)
        assert response.status_code == 200
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args["event"]["sender"]["sender_id"]["open_id"] == "ou_self_user"


def test_no_permission(client):
    from app.service.directory_service import UserInfo

    handler_mod = client._handler_mod
    dir_service = client._dir_service
    msg_service = client._msg_service

    user_zhang = UserInfo(
        user_id="u_zhang",
        open_id="ou_zhang",
        name="张三",
        employee_no="001",
        department_ids=["dept1"],
    )
    dir_service._by_name = {"张三": [user_zhang]}
    dir_service._by_open_id = {"ou_zhang": user_zhang}
    dir_service._by_user_id = {"u_zhang": user_zhang}

    from app.service.session_service import SessionService

    from app.service.message_handler import MessageHandler
    real_handler = MessageHandler(
        directory_service=dir_service,
        attendance_service=client._att_service,
        message_service=msg_service,
        session_service=SessionService(),
    )
    handler_mod.message_handler = real_handler

    msg_service._client.request = AsyncMock(return_value={})

    send_text_calls = []

    async def capture_send_text(open_id, text):
        send_text_calls.append((open_id, text))

    msg_service.send_text = AsyncMock(side_effect=capture_send_text)

    payload = make_message_event("ou_no_perm_user", "查 张三 上月")
    body = encrypt_event(payload)

    with patch("app.api.webhook._run_process_message_event") as mock_run:
        response = client.post("/webhook/lark/event", json=body)
        assert response.status_code == 200
        mock_run.assert_called_once()


def test_ambiguous_user_selection_flow(client):
    from app.service.directory_service import UserInfo
    from app.service.session_service import SessionService
    from app.service.message_handler import MessageHandler

    handler_mod = client._handler_mod
    dir_service = client._dir_service
    msg_service = client._msg_service
    att_service = client._att_service

    user_zhang1 = UserInfo(
        user_id="u_zhang1",
        open_id="ou_zhang1",
        name="张三",
        employee_no="001",
        department_ids=["dept1"],
    )
    user_zhang2 = UserInfo(
        user_id="u_zhang2",
        open_id="ou_zhang2",
        name="张三",
        employee_no="002",
        department_ids=["dept2"],
    )

    dir_service._by_name = {"张三": [user_zhang1, user_zhang2]}
    dir_service._by_open_id = {
        "ou_zhang1": user_zhang1,
        "ou_zhang2": user_zhang2,
        "ou_admin": UserInfo("u_admin", "ou_admin", "管理员", "000", []),
    }
    dir_service._by_user_id = {
        "u_zhang1": user_zhang1,
        "u_zhang2": user_zhang2,
    }

    session_service = SessionService()
    send_card_calls = []

    async def capture_send_card(open_id, card):
        send_card_calls.append((open_id, card))

    msg_service.send_card = AsyncMock(side_effect=capture_send_card)

    att_service.query_stats = AsyncMock(return_value={
        "u_zhang1": MagicMock(name="张三", user_id="u_zhang1", fields=[])
    })

    real_handler = MessageHandler(
        directory_service=dir_service,
        attendance_service=att_service,
        message_service=msg_service,
        session_service=session_service,
    )
    handler_mod.message_handler = real_handler

    payload1 = make_message_event("ou_admin", "查 张三 上月")
    body1 = encrypt_event(payload1)

    with patch("app.api.webhook._run_process_message_event") as mock_run1:
        response1 = client.post("/webhook/lark/event", json=body1)
        assert response1.status_code == 200
        mock_run1.assert_called_once()

    import asyncio
    asyncio.run(real_handler.handle_message(payload1))

    pending = session_service.get_pending_selection("ou_admin")
    assert pending is not None
    assert len(pending["candidates"]) == 2
    assert len(send_card_calls) == 1

    payload2 = make_message_event("ou_admin", "1")
    body2 = encrypt_event(payload2)

    with patch("app.api.webhook._run_process_message_event") as mock_run2:
        response2 = client.post("/webhook/lark/event", json=body2)
        assert response2.status_code == 200

    asyncio.run(real_handler.handle_message(payload2))

    att_service.query_stats.assert_called()
    assert len(send_card_calls) == 2
