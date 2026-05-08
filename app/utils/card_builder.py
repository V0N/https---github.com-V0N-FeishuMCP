from app.service.directory_service import UserInfo
from app.service.attendance_service import AttendanceResult, FieldData


def minutes_to_hm(minutes_str: str) -> str:
    try:
        total = int(minutes_str)
    except (ValueError, TypeError):
        return minutes_str

    if total == 0:
        return "0分钟"

    hours = total // 60
    mins = total % 60

    if hours > 0 and mins > 0:
        return f"{hours}小时{mins}分钟"
    elif hours > 0:
        return f"{hours}小时"
    else:
        return f"{mins}分钟"


def format_field_value(field_data: FieldData) -> str:
    title = field_data.title
    value = field_data.value

    if "时长" in title:
        return minutes_to_hm(value)
    elif "天数" in title:
        return value + "天"
    elif "次数" in title:
        return value + "次"
    else:
        return value


def build_attendance_card(
    user_info: UserInfo,
    time_label: str,
    result: AttendanceResult,
) -> dict:
    dept = user_info.department_ids[0] if user_info.department_ids else "无"

    info_lines = [
        f"**查询对象：** {user_info.name}",
        f"**时间范围：** {time_label}",
        f"**部门：** {dept}",
        f"**工号：** {user_info.employee_no}",
    ]
    info_text = "\n".join(info_lines)

    field_lines = []
    for fd in result.fields:
        formatted = format_field_value(fd)
        title_lower = fd.title
        if "加班" in title_lower or "出勤" in title_lower:
            emoji = "⏰"
        elif fd.is_abnormal:
            emoji = "⚠️"
        else:
            emoji = "✅"
        field_lines.append(f"{emoji} {fd.title}：{formatted}")

    fields_text = "\n".join(field_lines) if field_lines else "暂无考勤数据"

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "📊 考勤查询结果"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": info_text},
            },
            {"tag": "hr"},
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": fields_text},
            },
        ],
    }


def build_ambiguous_card(candidates: list[UserInfo]) -> dict:
    shown = candidates[:10]
    lines = []
    for i, user in enumerate(shown, start=1):
        dept = user.department_ids[0] if user.department_ids else "无"
        lines.append(
            f"{i}️⃣ {user.name}（工号：{user.employee_no}，部门：{dept}）"
        )
    content = "\n".join(lines)

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "🔍 找到多个同名用户，请选择"},
            "template": "yellow",
        },
        "elements": [
            {
                "tag": "div",
                "text": {"tag": "lark_md", "content": content},
            },
        ],
    }


def build_error_text(scenario: str, **kwargs) -> str:
    if scenario == "invalid_command":
        return (
            "❌ 指令格式错误，请参考以下示例：\n"
            "• 查我 上月\n"
            "• 查我 本月\n"
            "• 查他 张三 上月\n"
            "• 查他 张三 本月\n"
            "• 查他 张三 上季度"
        )
    elif scenario == "user_not_found":
        name = kwargs.get("name", "")
        return f"❌ 未找到姓名为「{name}」的员工，请确认姓名是否正确"
    elif scenario == "no_permission":
        return "❌ 你没有查询他人考勤的权限，仅可查询自己的考勤，发送「查我 上月」即可查询自己的考勤"
    elif scenario == "no_data":
        name = kwargs.get("name", "")
        time_range = kwargs.get("time_range", "")
        return f"ℹ️ {name}在{time_range}时间段内暂无考勤记录"
    elif scenario == "api_error":
        return "⚠️ 查询失败，请稍后重试，若多次失败请联系管理员"
    elif scenario == "partial_failure":
        failed_names = kwargs.get("failed_names", "")
        return f"⚠️ 部分用户查询失败：{failed_names}，其余结果如下："
    elif scenario == "selection_expired":
        return "⏰ 选择已过期，请重新发送查询指令"
    elif scenario == "selection_invalid":
        max_num = kwargs.get("max_num", "")
        return f"❌ 无效的序号，请回复1-{max_num}之间的数字"
    else:
        return "⚠️ 未知错误"
