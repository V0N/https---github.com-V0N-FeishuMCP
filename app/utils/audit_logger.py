import logging
import json
import time
from typing import Literal

ResultStatus = Literal["success", "not_found", "no_permission", "api_error"]


class AuditLogger:
    def __init__(self):
        self._logger = logging.getLogger("audit")

    def log_query(
        self,
        requester_open_id: str,
        requester_name: str,
        target_names: list[str],
        time_range: str,
        result_status: ResultStatus,
    ) -> None:
        record = {
            "event": "query",
            "requester_open_id": requester_open_id,
            "requester_name": requester_name,
            "target_names": target_names,
            "time_range": time_range,
            "result_status": result_status,
            "timestamp": time.time(),
        }
        self._logger.info(json.dumps(record, ensure_ascii=False))


audit_logger = AuditLogger()
