from unittest.mock import patch

from app.service.session_service import SessionService


def test_set_get_pending_selection():
    svc = SessionService()
    candidates = [{"name": "张三", "user_id": "u_001"}]
    query_params = {"month": "2026-01"}
    svc.set_pending_selection("ou_001", candidates, query_params)
    result = svc.get_pending_selection("ou_001")
    assert result is not None
    assert result["candidates"] == candidates
    assert result["query_params"] == query_params


def test_pending_selection_expired():
    svc = SessionService()
    with patch("app.service.session_service.time") as mock_time:
        mock_time.time.return_value = 0
        svc.set_pending_selection("ou_001", [], {})
        mock_time.time.return_value = 301
        result = svc.get_pending_selection("ou_001")
    assert result is None


def test_pending_selection_not_expired():
    svc = SessionService()
    candidates = [{"name": "李四", "user_id": "u_002"}]
    with patch("app.service.session_service.time") as mock_time:
        mock_time.time.return_value = 0
        svc.set_pending_selection("ou_002", candidates, {"month": "2026-02"})
        mock_time.time.return_value = 299
        result = svc.get_pending_selection("ou_002")
    assert result is not None
    assert result["candidates"] == candidates


def test_clear_pending_selection():
    svc = SessionService()
    svc.set_pending_selection("ou_003", [{"name": "王五"}], {})
    svc.clear_pending_selection("ou_003")
    result = svc.get_pending_selection("ou_003")
    assert result is None


def test_set_get_export_context():
    svc = SessionService()
    results = [{"name": "张三", "days": 22}]
    svc.set_export_context("ou_004", results, "2026年3月")
    got = svc.get_export_context("ou_004")
    assert got is not None
    assert got["results"] == results
    assert got["time_label"] == "2026年3月"


def test_export_context_expired():
    svc = SessionService()
    with patch("app.service.session_service.time") as mock_time:
        mock_time.time.return_value = 0
        svc.set_export_context("ou_005", [{"name": "赵六"}])
        mock_time.time.return_value = 601
        got = svc.get_export_context("ou_005")
    assert got is None
