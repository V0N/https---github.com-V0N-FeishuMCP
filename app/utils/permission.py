from app.config.settings import settings


def is_allowed(open_id: str) -> bool:
    if not settings or not settings.ALLOWED_USER_IDS:
        return False
    return open_id in settings.ALLOWED_USER_IDS


def check_query_permission(requester_open_id: str, target_open_ids: list) -> bool:
    if all(tid == requester_open_id for tid in target_open_ids):
        return True
    return is_allowed(requester_open_id)
