from unittest.mock import patch

import app.utils.permission as permission_module
from app.utils.permission import is_allowed, check_query_permission


def _mock_settings(allowed_ids: set):
    mock = type("Settings", (), {"ALLOWED_USER_IDS": allowed_ids})()
    return mock


def test_is_allowed_in_whitelist():
    with patch.object(permission_module, "settings", _mock_settings({"ou_admin"})):
        assert is_allowed("ou_admin") is True


def test_is_allowed_not_in_whitelist():
    with patch.object(permission_module, "settings", _mock_settings({"ou_admin"})):
        assert is_allowed("ou_user") is False


def test_is_allowed_empty_whitelist():
    with patch.object(permission_module, "settings", _mock_settings(set())):
        assert is_allowed("ou_anyone") is False


def test_query_permission_self_allowed():
    with patch.object(permission_module, "settings", _mock_settings(set())):
        assert check_query_permission("ou_self", ["ou_self"]) is True


def test_query_permission_others_need_whitelist():
    with patch.object(permission_module, "settings", _mock_settings({"ou_admin"})):
        assert check_query_permission("ou_admin", ["ou_admin", "ou_other"]) is True


def test_query_permission_others_not_in_whitelist():
    with patch.object(permission_module, "settings", _mock_settings({"ou_admin"})):
        assert check_query_permission("ou_user", ["ou_user", "ou_other"]) is False


def test_query_permission_empty_whitelist_others():
    with patch.object(permission_module, "settings", _mock_settings(set())):
        assert check_query_permission("ou_user", ["ou_user", "ou_other"]) is False
