import pytest
from unittest.mock import AsyncMock

from app.utils.feishu_client import FeishuClient
from app.service.directory_service import DirectoryService


def _dept_resp(items, has_more=False, page_token=""):
    return {"code": 0, "data": {"has_more": has_more, "page_token": page_token, "items": items}}


def _user_resp(items, has_more=False, page_token=""):
    return {"code": 0, "data": {"has_more": has_more, "page_token": page_token, "items": items}}


def _make_user(user_id, open_id, name, employee_no, department_ids):
    return {
        "user_id": user_id,
        "open_id": open_id,
        "name": name,
        "employee_no": employee_no,
        "department_ids": department_ids,
    }


async def test_sync_pagination():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([{"department_id": "d_001"}], has_more=True, page_token="tok1"),
        _dept_resp([{"department_id": "d_002"}], has_more=False),
        _user_resp([_make_user("u_1", "ou_1", "张三", "10001", ["0"])]),
        _user_resp([_make_user("u_2", "ou_2", "李四", "10002", ["d_001"])]),
        _user_resp([_make_user("u_3", "ou_3", "王五", "10003", ["d_002"])]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    assert client.request.call_count == 5


async def test_sync_multi_department():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([{"department_id": "d_a"}, {"department_id": "d_b"}], has_more=False),
        _user_resp([_make_user("u_1", "ou_1", "张三", "10001", ["0"])]),
        _user_resp([_make_user("u_2", "ou_2", "李四", "10002", ["d_a"])]),
        _user_resp([_make_user("u_3", "ou_3", "王五", "10003", ["d_b"])]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    find_dept_calls = [
        c for c in client.request.call_args_list
        if "/contact/v3/users/find_by_department" in c.args[1]
    ]
    assert len(find_dept_calls) == 3


async def test_sync_dedup_by_user_id():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([{"department_id": "d_a"}], has_more=False),
        _user_resp([_make_user("u_dup", "ou_dup", "重复用户", "99999", ["0"])]),
        _user_resp([_make_user("u_dup", "ou_dup", "重复用户", "99999", ["d_a"])]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    assert len(service._by_user_id) == 1
    assert "u_dup" in service._by_user_id


async def test_find_by_name_same_name():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([], has_more=False),
        _user_resp([
            _make_user("u_1", "ou_1", "李明", "10001", ["0"]),
            _make_user("u_2", "ou_2", "李明", "10002", ["0"]),
        ]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    result = service.find_by_name("李明")
    assert len(result) == 2
    user_ids = {u.user_id for u in result}
    assert user_ids == {"u_1", "u_2"}


async def test_find_by_name_not_found():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([], has_more=False),
        _user_resp([_make_user("u_1", "ou_1", "张三", "10001", ["0"])]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    result = service.find_by_name("不存在的人")
    assert result == []


async def test_find_by_open_id():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([], has_more=False),
        _user_resp([_make_user("u_1", "ou_abc", "赵六", "10010", ["0"])]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    user = service.find_by_open_id("ou_abc")
    assert user is not None
    assert user.user_id == "u_1"
    assert user.name == "赵六"

    assert service.find_by_open_id("ou_not_exist") is None


async def test_find_by_user_id():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _dept_resp([], has_more=False),
        _user_resp([_make_user("u_xyz", "ou_xyz", "孙七", "10020", ["0"])]),
    ])
    service = DirectoryService(client)
    await service.sync_all()

    user = service.find_by_user_id("u_xyz")
    assert user is not None
    assert user.open_id == "ou_xyz"
    assert user.name == "孙七"

    assert service.find_by_user_id("u_not_exist") is None
