import json

from app.service.directory_service import UserInfo
from app.service.attendance_service import AttendanceResult, FieldData
from app.utils.card_builder import (
    minutes_to_hm,
    build_attendance_card,
    build_ambiguous_card,
    build_error_text,
)


def make_user(
    name="张三",
    user_id="u_001",
    open_id="ou_001",
    employee_no="10001",
    dept=None,
):
    if dept is None:
        dept = ["d_001"]
    return UserInfo(
        user_id=user_id,
        open_id=open_id,
        name=name,
        employee_no=employee_no,
        department_ids=dept,
    )


def make_result(name="张三", user_id="u_001", fields=None):
    if fields is None:
        fields = [
            FieldData(code="50201", title="应出勤天数", value="22", is_abnormal=False),
            FieldData(code="50202", title="实际出勤天数", value="20", is_abnormal=False),
            FieldData(code="50301", title="迟到次数", value="2", is_abnormal=True),
            FieldData(code="50401", title="迟到时长", value="90", is_abnormal=True),
            FieldData(code="50501", title="加班总时长", value="60", is_abnormal=False),
        ]
    return AttendanceResult(name=name, user_id=user_id, fields=fields)


def test_minutes_to_hm_zero():
    assert minutes_to_hm("0") == "0分钟"


def test_minutes_to_hm_exact_hour():
    assert minutes_to_hm("60") == "1小时"


def test_minutes_to_hm_mixed():
    assert minutes_to_hm("90") == "1小时30分钟"


def test_minutes_to_hm_non_numeric():
    assert minutes_to_hm("N/A") == "N/A"


def test_build_attendance_card_structure():
    user = make_user()
    result = make_result()
    card = build_attendance_card(user, "2026年3月", result)

    assert card["header"]["template"] == "blue"
    assert len(card["elements"]) >= 3


def test_build_attendance_card_contains_name():
    user = make_user(name="李四")
    result = make_result(name="李四")
    card = build_attendance_card(user, "2026年3月", result)
    card_json = json.dumps(card, ensure_ascii=False)

    assert "李四" in card_json


def test_build_attendance_card_abnormal_marker():
    user = make_user()
    abnormal_field = FieldData(
        code="50301", title="迟到次数", value="3", is_abnormal=True
    )
    result = make_result(fields=[abnormal_field])
    card = build_attendance_card(user, "2026年3月", result)
    card_json = json.dumps(card, ensure_ascii=False)

    assert "⚠️" in card_json


def test_build_ambiguous_card_structure():
    candidates = [make_user(name=f"用户{i}", user_id=f"u_{i}", open_id=f"ou_{i}", employee_no=str(10000 + i)) for i in range(3)]
    card = build_ambiguous_card(candidates)

    assert card["header"]["template"] == "yellow"


def test_build_ambiguous_card_contains_candidates():
    names = ["赵一", "钱二", "孙三"]
    candidates = [
        make_user(name=n, user_id=f"u_{i}", open_id=f"ou_{i}", employee_no=str(10000 + i))
        for i, n in enumerate(names)
    ]
    card = build_ambiguous_card(candidates)
    card_json = json.dumps(card, ensure_ascii=False)

    for name in names:
        assert name in card_json


def test_build_error_text_user_not_found():
    text = build_error_text("user_not_found", name="王五")
    assert "王五" in text


def test_build_error_text_no_permission():
    text = build_error_text("no_permission")
    assert "没有查询他人考勤的权限" in text


def test_build_error_text_no_data():
    text = build_error_text("no_data", name="张三", time_range="2026年3月")
    assert "张三" in text
    assert "2026年3月" in text
