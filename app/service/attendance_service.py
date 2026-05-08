from dataclasses import dataclass, field
from typing import Optional
import logging

from app.utils.feishu_client import FeishuClient, FeishuAPIError

logger = logging.getLogger(__name__)


@dataclass
class FieldData:
    code: str
    title: str
    value: str
    is_abnormal: bool = False


@dataclass
class AttendanceResult:
    name: str
    user_id: str
    fields: list[FieldData] = field(default_factory=list)


TARGET_FIELD_TITLES = [
    "应出勤天数",
    "实际出勤天数",
    "迟到次数",
    "迟到时长",
    "早退次数",
    "上班缺卡次数",
    "下班缺卡次数",
    "旷工天数",
    "加班总时长",
]


class AttendanceService:
    def __init__(self, client, admin_user_id: str):
        self._client = client
        self._admin_user_id = admin_user_id
        self._field_map: dict[str, str] = {}
        self._target_codes: list[str] = []

    async def initialize(self):
        try:
            resp = await self._client.request(
                "GET",
                "/attendance/v1/user_stats_fields/query",
                params={
                    "employee_type": "employee_id",
                    "locale": "zh",
                    "stats_type": "month",
                    "user_id": self._admin_user_id,
                },
            )
            fields = (
                resp.get("data", {})
                .get("user_stats_fields", {})
                .get("fields", [])
            )
            field_map: dict[str, str] = {}
            title_to_code: dict[str, str] = {}
            for f in fields:
                code = f.get("code", "")
                title = f.get("title", "")
                if code:
                    field_map[code] = title
                    if title:
                        title_to_code[title] = code
                for cf in f.get("child_fields", []):
                    c_code = cf.get("code", "")
                    c_title = cf.get("title", "")
                    if c_code:
                        field_map[c_code] = c_title
                        if c_title:
                            title_to_code[c_title] = c_code
            self._field_map = field_map
            self._target_codes = [
                title_to_code[t] for t in TARGET_FIELD_TITLES if t in title_to_code
            ]
        except Exception as e:
            logger.error("初始化考勤字段失败: %s", e)
            return

        try:
            await self._client.request(
                "POST",
                "/attendance/v1/user_stats_views/update",
                params={"employee_type": "employee_id"},
                json={
                    "view": {
                        "stats_type": "month",
                        "user_id": self._admin_user_id,
                        "items": [
                            {"code": c, "child_codes": []} for c in self._target_codes
                        ],
                    }
                },
            )
        except Exception as e:
            logger.error("更新考勤视图失败: %s", e)

    async def query_stats(
        self,
        user_ids: list[str],
        time_ranges: list[tuple[int, int]],
    ) -> dict[str, AttendanceResult]:
        results: dict[str, AttendanceResult] = {}

        batch_size = 20
        batches = [user_ids[i: i + batch_size] for i in range(0, len(user_ids), batch_size)]

        for start_date, end_date in time_ranges:
            for batch in batches:
                try:
                    resp = await self._client.request(
                        "POST",
                        "/attendance/v1/user_stats_datas/query",
                        params={"employee_type": "employee_id"},
                        json={
                            "locale": "zh",
                            "stats_type": "month",
                            "start_date": start_date,
                            "end_date": end_date,
                            "user_ids": batch,
                            "user_id": self._admin_user_id,
                            "need_history": True,
                            "current_group_only": False,
                        },
                    )
                except Exception as e:
                    logger.error("查询考勤数据失败: %s", e)
                    continue

                user_datas = resp.get("data", {}).get("user_datas", [])
                for ud in user_datas:
                    uid = ud.get("user_id", "")
                    name = ud.get("name", "")
                    datas = ud.get("datas", [])

                    if uid not in results:
                        results[uid] = AttendanceResult(name=name, user_id=uid)
                        existing_map: dict[str, FieldData] = {}
                    else:
                        existing_map = {fd.code: fd for fd in results[uid].fields}

                    for item in datas:
                        code = item.get("code", "")
                        title = item.get("title", "")
                        value = item.get("value", "")
                        features = item.get("features", [])
                        is_abnormal = any(
                            f.get("key") == "Abnormal" and f.get("value") == "true"
                            for f in features
                        )

                        if code in existing_map:
                            fd = existing_map[code]
                            try:
                                fd.value = str(float(fd.value) + float(value))
                            except (ValueError, TypeError):
                                fd.value = value
                            fd.is_abnormal = is_abnormal
                        else:
                            fd = FieldData(
                                code=code,
                                title=title,
                                value=value,
                                is_abnormal=is_abnormal,
                            )
                            existing_map[code] = fd
                            results[uid].fields.append(fd)

        return results


from app.utils.feishu_client import feishu_client
from app.config.settings import settings

attendance_service = AttendanceService(
    feishu_client,
    settings.FEISHU_ADMIN_USER_ID if settings else "",
)
