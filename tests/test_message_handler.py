import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

import app.utils.permission as permission_module
from app.service.attendance_service import AttendanceResult, FieldData
from app.service.directory_service import DirectoryService, UserInfo
from app.service.attendance_service import AttendanceService
from app.service.message_service import MessageService
from app.service.session_service import SessionService
from app.service.message_handler import MessageHandler


def _make_user(user_id: str, open_id: str, name: str) -> UserInfo:
    return UserInfo(
        user_id=user_id,
        open_id=open_id,
        name=name,
        employee_no=f"EMP_{user_id}",
        department_ids=["dept_001"],
    )


def _make_result(user_id: str, name: str) -> AttendanceResult:
    return AttendanceResult(
        name=name,
        user_id=user_id,
        fields=[
            FieldData(code="F001", title="实际出勤天数", value="20", is_abnormal=False)
        ],
    )


def _make_event(open_id: str, text: str) -> dict:
    return {
        "schema": "2.0",
        "event": {
            "sender": {"sender_id": {"open_id": open_id}},
            "message": {
                "content": json.dumps({"text": text}),
                "message_type": "text",
            },
        },
    }


@pytest.fixture
def services():
    dir_svc = Mock(spec=DirectoryService)
    att_svc = Mock(spec=AttendanceService)
    att_svc.query_stats = AsyncMock()
    msg_svc = Mock(spec=MessageService)
    msg_svc.send_text = AsyncMock()
    msg_svc.send_card = AsyncMock()
    sess_svc = SessionService()
    return MessageHandler(dir_svc, att_svc, msg_svc, sess_svc)


@pytest.mark.asyncio
async def test_handle_query_one_unique_user(services: MessageHandler):
    handler = services
    user1 = _make_user("u_001", "ou_001", "张三")
    result1 = _make_result("u_001", "张三")

    handler._directory_service.find_by_name.return_value = [user1]
    handler._attendance_service.query_stats.return_value = {"u_001": result1}

    mock_settings = type("S", (), {"ALLOWED_USER_IDS": {"ou_requester"}})()
    with patch.object(permission_module, "settings", mock_settings):
        await handler.handle_query_one("ou_requester", "张三", "上月")

    handler._message_service.send_card.assert_called_once()


@pytest.mark.asyncio
async def test_handle_query_one_ambiguous(services: MessageHandler):
    handler = services
    user1 = _make_user("u_001", "ou_001", "张三")
    user2 = _make_user("u_002", "ou_002", "张三")

    handler._directory_service.find_by_name.return_value = [user1, user2]

    await handler.handle_query_one("ou_requester", "张三", "上月")

    handler._message_service.send_card.assert_called_once()
    pending = handler._session_service.get_pending_selection("ou_requester")
    assert pending is not None
    assert len(pending["candidates"]) == 2


@pytest.mark.asyncio
async def test_handle_query_one_not_found(services: MessageHandler):
    handler = services
    handler._directory_service.find_by_name.return_value = []

    await handler.handle_query_one("ou_requester", "不存在的人", "上月")

    handler._message_service.send_text.assert_called_once()
    call_args = handler._message_service.send_text.call_args
    assert "未找到" in call_args[0][1]


@pytest.mark.asyncio
async def test_handle_message_select_priority(services: MessageHandler):
    handler = services
    user1 = _make_user("u_001", "ou_001", "张三")
    user2 = _make_user("u_002", "ou_002", "张三")
    result1 = _make_result("u_001", "张三")

    handler._session_service.set_pending_selection(
        "ou_requester",
        [user1, user2],
        {"time_text": "上月"},
    )
    handler._attendance_service.query_stats.return_value = {"u_001": result1}

    event_data = _make_event("ou_requester", "1")
    await handler.handle_message(event_data)

    handler._attendance_service.query_stats.assert_called_once()


@pytest.mark.asyncio
async def test_handle_query_self(services: MessageHandler):
    handler = services
    user1 = _make_user("u_001", "ou_self", "李四")
    result1 = _make_result("u_001", "李四")

    handler._directory_service.find_by_open_id.return_value = user1
    handler._attendance_service.query_stats.return_value = {"u_001": result1}

    await handler.handle_query_self("ou_self", "上月")

    handler._message_service.send_card.assert_called_once()


@pytest.mark.asyncio
async def test_handle_query_batch_sends_multiple_cards(services: MessageHandler):
    handler = services
    user1 = _make_user("u_001", "ou_001", "张三")
    user2 = _make_user("u_002", "ou_002", "李四")
    r1 = _make_result("u_001", "张三")
    r2 = _make_result("u_002", "李四")

    handler._directory_service.find_by_name.side_effect = lambda name: (
        [user1] if name == "张三" else [user2]
    )
    handler._attendance_service.query_stats.return_value = {"u_001": r1, "u_002": r2}

    mock_settings = type("S", (), {"ALLOWED_USER_IDS": {"ou_admin"}})()
    with patch.object(permission_module, "settings", mock_settings):
        await handler.handle_query_batch("ou_admin", ["张三", "李四"], "上月")

    assert handler._message_service.send_card.call_count == 2


@pytest.mark.asyncio
async def test_handle_no_permission(services: MessageHandler):
    handler = services
    target_user = _make_user("u_target", "ou_target", "王五")

    handler._directory_service.find_by_name.return_value = [target_user]

    mock_settings = type("S", (), {"ALLOWED_USER_IDS": set()})()
    with patch.object(permission_module, "settings", mock_settings):
        await handler.handle_query_one("ou_not_admin", "王五", "上月")

    handler._message_service.send_text.assert_called_once()
    call_args = handler._message_service.send_text.call_args
    assert "权限" in call_args[0][1]
