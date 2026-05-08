import logging
import json
from app.service.directory_service import DirectoryService, UserInfo
from app.service.attendance_service import AttendanceService
from app.service.message_service import MessageService
from app.service.session_service import SessionService
from app.service.export_service import generate_excel
from app.utils.command_parser import parse_command
from app.utils.time_parser import parse_time_range, format_time_range_label
from app.utils.card_builder import (
    build_attendance_card, build_ambiguous_card, build_error_text
)
from app.utils.permission import check_query_permission

logger = logging.getLogger(__name__)


class MessageHandler:
    def __init__(
        self,
        directory_service: DirectoryService,
        attendance_service: AttendanceService,
        message_service: MessageService,
        session_service: SessionService,
    ):
        self._directory_service = directory_service
        self._attendance_service = attendance_service
        self._message_service = message_service
        self._session_service = session_service

    async def handle_message(self, event_data: dict) -> None:
        event = event_data.get("event", {})
        sender = event.get("sender", {})
        sender_id = sender.get("sender_id", {})
        open_id = sender_id.get("open_id", "")

        message = event.get("message", {})
        content_str = message.get("content", "{}")
        try:
            content = json.loads(content_str)
        except (json.JSONDecodeError, TypeError):
            content = {}
        text = content.get("text", "").strip()

        pending = self._session_service.get_pending_selection(open_id)
        if pending is not None:
            if text.isdigit():
                await self.handle_selection(open_id, text)
                return
            else:
                self._session_service.clear_pending_selection(open_id)

        cmd = parse_command(text)

        if cmd.type == "query_one":
            await self.handle_query_one(open_id, cmd.names[0] if cmd.names else "", cmd.time_text)
        elif cmd.type == "query_self":
            await self.handle_query_self(open_id, cmd.time_text)
        elif cmd.type == "query_batch":
            await self.handle_query_batch(open_id, cmd.names, cmd.time_text)
        elif cmd.type == "export":
            await self.handle_export(open_id)
        else:
            await self._message_service.send_text(open_id, build_error_text("invalid_command"))

    async def handle_query_one(self, open_id: str, name: str, time_text: str) -> None:
        candidates = self._directory_service.find_by_name(name)

        if not candidates:
            await self._message_service.send_text(
                open_id, build_error_text("user_not_found", name=name)
            )
            return

        if len(candidates) > 1:
            self._session_service.set_pending_selection(
                open_id, candidates, {"time_text": time_text}
            )
            await self._message_service.send_card(open_id, build_ambiguous_card(candidates))
            return

        user = candidates[0]
        if user.open_id != open_id:
            if not check_query_permission(open_id, [user.open_id]):
                await self._message_service.send_text(
                    open_id, build_error_text("no_permission")
                )
                return

        time_ranges = parse_time_range(time_text)
        time_label = format_time_range_label(time_ranges)
        results = await self._attendance_service.query_stats([user.user_id], time_ranges)

        if not results or user.user_id not in results:
            await self._message_service.send_text(
                open_id, build_error_text("no_data", name=name, time_range=time_label)
            )
            return

        result = results[user.user_id]
        await self._message_service.send_card(
            open_id, build_attendance_card(user, time_label, result)
        )
        self._session_service.set_export_context(open_id, [result], time_label)

    async def handle_query_self(self, open_id: str, time_text: str) -> None:
        user = self._directory_service.find_by_open_id(open_id)

        if user is None:
            try:
                resp = await self._attendance_service._client.request(
                    "GET",
                    f"/contact/v3/users/{open_id}",
                    params={"user_id_type": "open_id"},
                )
                user_data = resp.get("data", {}).get("user", {})
                user_id = user_data.get("user_id", "")
                if not user_id:
                    await self._message_service.send_text(
                        open_id, "无法获取您的信息，请联系管理员"
                    )
                    return
                user = UserInfo(
                    user_id=user_id,
                    open_id=open_id,
                    name=user_data.get("name", ""),
                    employee_no=user_data.get("employee_no", ""),
                    department_ids=user_data.get("department_ids", []),
                )
            except Exception as e:
                logger.error("通过 open_id 获取用户信息失败: %s", e)
                await self._message_service.send_text(
                    open_id, "无法获取您的信息，请联系管理员"
                )
                return

        time_ranges = parse_time_range(time_text)
        time_label = format_time_range_label(time_ranges)
        results = await self._attendance_service.query_stats([user.user_id], time_ranges)

        if not results or user.user_id not in results:
            await self._message_service.send_text(
                open_id, build_error_text("no_data", name=user.name, time_range=time_label)
            )
            return

        result = results[user.user_id]
        await self._message_service.send_card(
            open_id, build_attendance_card(user, time_label, result)
        )
        self._session_service.set_export_context(open_id, [result], time_label)

    async def handle_query_batch(self, open_id: str, names: list[str], time_text: str) -> None:
        if not check_query_permission(open_id, []):
            await self._message_service.send_text(
                open_id, build_error_text("no_permission")
            )
            return

        failed_names = []
        warn_names = []
        users_to_query: list[UserInfo] = []

        for name in names:
            candidates = self._directory_service.find_by_name(name)
            if not candidates:
                failed_names.append(name)
            elif len(candidates) > 1:
                warn_names.append(name)
                users_to_query.append(candidates[0])
            else:
                users_to_query.append(candidates[0])

        if failed_names:
            await self._message_service.send_text(
                open_id,
                build_error_text("partial_failure", failed_names="、".join(failed_names)),
            )

        if not users_to_query:
            return

        all_user_ids = [u.user_id for u in users_to_query]
        time_ranges = parse_time_range(time_text)
        time_label = format_time_range_label(time_ranges)
        results = await self._attendance_service.query_stats(all_user_ids, time_ranges)

        for user in users_to_query:
            if user.user_id in results:
                result = results[user.user_id]
                await self._message_service.send_card(
                    open_id, build_attendance_card(user, time_label, result)
                )

        if results:
            self._session_service.set_export_context(open_id, list(results.values()), time_label)

    async def handle_selection(self, open_id: str, index_str: str) -> None:
        pending = self._session_service.get_pending_selection(open_id)
        if pending is None:
            await self._message_service.send_text(
                open_id, build_error_text("selection_expired")
            )
            return

        candidates = pending["candidates"]
        query_params = pending["query_params"]

        try:
            index = int(index_str)
        except ValueError:
            await self._message_service.send_text(
                open_id,
                build_error_text("selection_invalid", max_num=len(candidates)),
            )
            return

        if index < 1 or index > len(candidates):
            await self._message_service.send_text(
                open_id,
                build_error_text("selection_invalid", max_num=len(candidates)),
            )
            return

        user = candidates[index - 1]
        self._session_service.clear_pending_selection(open_id)

        time_text = query_params.get("time_text", "")
        time_ranges = parse_time_range(time_text)
        time_label = format_time_range_label(time_ranges)
        results = await self._attendance_service.query_stats([user.user_id], time_ranges)

        if not results or user.user_id not in results:
            await self._message_service.send_text(
                open_id,
                build_error_text("no_data", name=user.name, time_range=time_label),
            )
            return

        result = results[user.user_id]
        await self._message_service.send_card(
            open_id, build_attendance_card(user, time_label, result)
        )
        self._session_service.set_export_context(open_id, [result], time_label)

    async def handle_export(self, open_id: str) -> None:
        ctx = self._session_service.get_export_context(open_id)
        if ctx is None:
            await self._message_service.send_text(
                open_id, "⚠️ 没有可导出的数据，请先查询考勤后再导出"
            )
            return

        results = ctx["results"]
        time_label = ctx["time_label"]

        user_map: dict[str, UserInfo] = {}
        for result in results:
            user = self._directory_service.find_by_user_id(result.user_id)
            if user:
                user_map[result.user_id] = user

        try:
            excel_bytes = generate_excel(results, user_map, time_label)
        except Exception:
            await self._message_service.send_text(
                open_id, build_error_text("api_error")
            )
            return

        file_name = f"考勤报表_{time_label}.xlsx"
        try:
            upload_resp = await self._attendance_service._client.request(
                "POST",
                "/im/v1/files",
                files={
                    "file_type": (None, "xlsx"),
                    "file_name": (None, file_name),
                    "file": (file_name, excel_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                },
            )
            file_key = upload_resp.get("data", {}).get("file_key", "")
        except Exception:
            await self._message_service.send_text(
                open_id, build_error_text("api_error")
            )
            return

        try:
            await self._attendance_service._client.request(
                "POST",
                "/im/v1/messages",
                params={"receive_id_type": "open_id"},
                json={
                    "receive_id": open_id,
                    "msg_type": "file",
                    "content": json.dumps({"file_key": file_key}),
                },
            )
        except Exception:
            await self._message_service.send_text(
                open_id, build_error_text("api_error")
            )


from app.service.directory_service import directory_service
from app.service.message_service import message_service

message_handler: MessageHandler = None
