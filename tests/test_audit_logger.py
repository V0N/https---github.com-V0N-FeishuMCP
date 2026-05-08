import json
import logging
from unittest.mock import patch

import pytest

from app.utils.audit_logger import AuditLogger


@pytest.fixture()
def logger():
    return AuditLogger()


def _last_record(caplog) -> dict:
    msg = caplog.records[-1].getMessage()
    return json.loads(msg)


def test_log_query_success(caplog, logger):
    with caplog.at_level(logging.INFO, logger="audit"):
        logger.log_query(
            requester_open_id="ou_abc123",
            requester_name="张三",
            target_names=["李四", "王五"],
            time_range="2026年3月",
            result_status="success",
        )

    data = _last_record(caplog)
    assert data["event"] == "query"
    assert data["requester_open_id"] == "ou_abc123"
    assert data["target_names"] == ["李四", "王五"]
    assert data["result_status"] == "success"
    assert "timestamp" in data


def test_log_query_not_found(caplog, logger):
    with caplog.at_level(logging.INFO, logger="audit"):
        logger.log_query(
            requester_open_id="ou_xyz",
            requester_name="",
            target_names=["赵六"],
            time_range="2026年4月",
            result_status="not_found",
        )

    data = _last_record(caplog)
    assert data["event"] == "query"
    assert data["requester_open_id"] == "ou_xyz"
    assert data["target_names"] == ["赵六"]
    assert data["result_status"] == "not_found"


def test_log_query_no_permission(caplog, logger):
    with caplog.at_level(logging.INFO, logger="audit"):
        logger.log_query(
            requester_open_id="ou_noperm",
            requester_name="钱七",
            target_names=["孙八"],
            time_range="2026年1月",
            result_status="no_permission",
        )

    data = _last_record(caplog)
    assert data["event"] == "query"
    assert data["requester_open_id"] == "ou_noperm"
    assert data["target_names"] == ["孙八"]
    assert data["result_status"] == "no_permission"


def test_log_query_api_error(caplog, logger):
    with caplog.at_level(logging.INFO, logger="audit"):
        logger.log_query(
            requester_open_id="ou_apierr",
            requester_name="周九",
            target_names=["吴十"],
            time_range="2025年12月",
            result_status="api_error",
        )

    data = _last_record(caplog)
    assert data["event"] == "query"
    assert data["requester_open_id"] == "ou_apierr"
    assert data["target_names"] == ["吴十"]
    assert data["result_status"] == "api_error"


def test_log_query_timestamp(caplog, logger):
    fixed_time = 1746000000.0
    with patch("app.utils.audit_logger.time.time", return_value=fixed_time):
        with caplog.at_level(logging.INFO, logger="audit"):
            logger.log_query(
                requester_open_id="ou_ts",
                requester_name="测试用户",
                target_names=["目标用户"],
                time_range="2026年2月",
                result_status="success",
            )

    data = _last_record(caplog)
    assert data["timestamp"] == fixed_time
