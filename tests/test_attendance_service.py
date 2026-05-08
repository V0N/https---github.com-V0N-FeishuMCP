import pytest
from unittest.mock import AsyncMock

from app.utils.feishu_client import FeishuClient, FeishuAPIError
from app.service.attendance_service import AttendanceService, TARGET_FIELD_TITLES


def _fields_resp(fields):
    return {
        "code": 0,
        "data": {
            "user_stats_fields": {
                "fields": fields
            }
        },
    }


def _view_resp():
    return {"code": 0, "data": {}}


def _stats_resp(user_datas):
    return {"code": 0, "data": {"user_datas": user_datas}}


def _make_field(code, title):
    return {"code": code, "title": title, "child_fields": []}


def _make_user_data(user_id, name, datas):
    return {"user_id": user_id, "name": name, "datas": datas}


def _make_data_item(code, title, value, abnormal=False):
    return {
        "code": code,
        "title": title,
        "value": value,
        "features": [{"key": "Abnormal", "value": "true" if abnormal else "false"}],
    }


async def test_initialize_builds_field_map():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _fields_resp([
            _make_field("50102", "姓名"),
            _make_field("50201", "应出勤天数"),
            _make_field("50202", "实际出勤天数"),
        ]),
        _view_resp(),
    ])
    service = AttendanceService(client, "admin_uid")
    await service.initialize()

    assert service._field_map["50102"] == "姓名"
    assert service._field_map["50201"] == "应出勤天数"
    assert service._field_map["50202"] == "实际出勤天数"


async def test_initialize_finds_target_codes():
    all_fields = [_make_field(str(1000 + i), title) for i, title in enumerate(TARGET_FIELD_TITLES)]
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _fields_resp(all_fields),
        _view_resp(),
    ])
    service = AttendanceService(client, "admin_uid")
    await service.initialize()

    assert len(service._target_codes) == len(TARGET_FIELD_TITLES)
    for i, title in enumerate(TARGET_FIELD_TITLES):
        expected_code = str(1000 + i)
        assert expected_code in service._target_codes


async def test_initialize_failure_no_exception():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=FeishuAPIError(99999, "mock error"))
    service = AttendanceService(client, "admin_uid")

    await service.initialize()

    assert service._field_map == {}
    assert service._target_codes == []


async def test_query_stats_batch_split():
    user_ids = [f"u_{i}" for i in range(21)]
    client = FeishuClient.__new__(FeishuClient)

    def make_batch_resp(batch_ids):
        user_datas = [
            _make_user_data(uid, f"name_{uid}", [
                _make_data_item("50201", "实际出勤天数", "10")
            ])
            for uid in batch_ids
        ]
        return _stats_resp(user_datas)

    client.request = AsyncMock(side_effect=[
        make_batch_resp(user_ids[:20]),
        make_batch_resp(user_ids[20:]),
    ])
    service = AttendanceService(client, "admin_uid")
    result = await service.query_stats(user_ids, [(20260101, 20260131)])

    assert client.request.call_count == 2
    assert len(result) == 21


async def test_query_stats_quarter_sum():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(side_effect=[
        _stats_resp([_make_user_data("u_001", "张三", [_make_data_item("50201", "实际出勤天数", "5")])]),
        _stats_resp([_make_user_data("u_001", "张三", [_make_data_item("50201", "实际出勤天数", "5")])]),
        _stats_resp([_make_user_data("u_001", "张三", [_make_data_item("50201", "实际出勤天数", "5")])]),
    ])
    service = AttendanceService(client, "admin_uid")
    time_ranges = [
        (20260101, 20260131),
        (20260201, 20260228),
        (20260301, 20260331),
    ]
    result = await service.query_stats(["u_001"], time_ranges)

    assert "u_001" in result
    fields = {fd.code: fd for fd in result["u_001"].fields}
    assert "50201" in fields
    value = fields["50201"].value
    assert float(value) == 15.0


async def test_query_stats_empty_response():
    client = FeishuClient.__new__(FeishuClient)
    client.request = AsyncMock(return_value=_stats_resp([]))
    service = AttendanceService(client, "admin_uid")
    result = await service.query_stats(["u_001"], [(20260101, 20260131)])

    assert result == {}
