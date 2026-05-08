import time
from typing import Optional


class SessionService:
    def __init__(self):
        self._pending_selection: dict = {}
        self._export_context: dict = {}

    def set_pending_selection(self, open_id: str, candidates: list, query_params: dict) -> None:
        self._pending_selection[open_id] = {
            "candidates": candidates,
            "query_params": query_params,
            "expire_at": time.time() + 300,
        }

    def get_pending_selection(self, open_id: str) -> Optional[dict]:
        entry = self._pending_selection.get(open_id)
        if entry is None:
            return None
        if time.time() > entry["expire_at"]:
            del self._pending_selection[open_id]
            return None
        return {"candidates": entry["candidates"], "query_params": entry["query_params"]}

    def clear_pending_selection(self, open_id: str) -> None:
        self._pending_selection.pop(open_id, None)

    def set_export_context(self, open_id: str, results: list, time_label: str = "") -> None:
        self._export_context[open_id] = {
            "results": results,
            "time_label": time_label,
            "expire_at": time.time() + 600,
        }

    def get_export_context(self, open_id: str) -> Optional[dict]:
        entry = self._export_context.get(open_id)
        if entry is None:
            return None
        if time.time() > entry["expire_at"]:
            del self._export_context[open_id]
            return None
        return {"results": entry["results"], "time_label": entry["time_label"]}


session_service = SessionService()
