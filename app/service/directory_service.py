from dataclasses import dataclass
from typing import Optional
import logging
import time

from app.utils.feishu_client import FeishuClient

logger = logging.getLogger(__name__)


@dataclass
class UserInfo:
    user_id: str
    open_id: str
    name: str
    employee_no: str
    department_ids: list[str]


class DirectoryService:
    """
    通讯录同步服务，维护内存中的员工目录
    """

    def __init__(self, client: FeishuClient):
        self._client = client
        self._by_name: dict[str, list[UserInfo]] = {}
        self._by_open_id: dict[str, UserInfo] = {}
        self._by_user_id: dict[str, UserInfo] = {}

    async def sync_all(self):
        start = time.time()
        users: dict[str, UserInfo] = {}

        department_ids = ["0"]

        try:
            page_token = None
            while True:
                params = {
                    "department_id": "0",
                    "fetch_child": True,
                    "page_size": 50,
                }
                if page_token:
                    params["page_token"] = page_token

                try:
                    resp = await self._client.request(
                        "GET",
                        "/contact/v3/departments/children",
                        params=params,
                    )
                    data = resp.get("data", {})
                    for item in data.get("items", []):
                        dept_id = item.get("department_id")
                        if dept_id:
                            department_ids.append(dept_id)
                    if not data.get("has_more", False):
                        break
                    page_token = data.get("page_token")
                except Exception as e:
                    logger.error("拉取子部门列表失败: %s", e)
                    break

            for dept_id in department_ids:
                page_token = None
                while True:
                    params = {
                        "department_id": dept_id,
                        "department_id_type": "department_id",
                        "user_id_type": "user_id",
                        "page_size": 50,
                    }
                    if page_token:
                        params["page_token"] = page_token

                    try:
                        resp = await self._client.request(
                            "GET",
                            "/contact/v3/users/find_by_department",
                            params=params,
                        )
                        data = resp.get("data", {})
                        for item in data.get("items", []):
                            uid = item.get("user_id")
                            if uid and uid not in users:
                                users[uid] = UserInfo(
                                    user_id=uid,
                                    open_id=item.get("open_id", ""),
                                    name=item.get("name", ""),
                                    employee_no=item.get("employee_no", ""),
                                    department_ids=item.get("department_ids", []),
                                )
                        if not data.get("has_more", False):
                            break
                        page_token = data.get("page_token")
                    except Exception as e:
                        logger.error("拉取部门 %s 成员失败: %s", dept_id, e)
                        break

        except Exception as e:
            logger.error("sync_all 发生未预期异常: %s", e)

        self._update_indexes(users)
        elapsed = time.time() - start
        logger.info("通讯录同步完成，耗时 %.2f 秒，员工总数 %d", elapsed, len(users))

    def find_by_name(self, name: str) -> list[UserInfo]:
        return self._by_name.get(name, [])

    def find_by_open_id(self, open_id: str) -> Optional[UserInfo]:
        return self._by_open_id.get(open_id)

    def find_by_user_id(self, user_id: str) -> Optional[UserInfo]:
        return self._by_user_id.get(user_id)

    def _update_indexes(self, users: dict[str, UserInfo]):
        by_name: dict[str, list[UserInfo]] = {}
        by_open_id: dict[str, UserInfo] = {}
        by_user_id: dict[str, UserInfo] = {}

        for user in users.values():
            by_user_id[user.user_id] = user
            by_open_id[user.open_id] = user
            by_name.setdefault(user.name, []).append(user)

        self._by_name = by_name
        self._by_open_id = by_open_id
        self._by_user_id = by_user_id


from app.utils.feishu_client import feishu_client
directory_service = DirectoryService(feishu_client)
