import pytest

from app.config.settings import load_settings

BASE_ENV = {
    "FEISHU_APP_ID": "app_id_test",
    "FEISHU_APP_SECRET": "app_secret_test",
    "FEISHU_ENCRYPT_KEY": "encrypt_key_test",
    "FEISHU_ADMIN_USER_ID": "admin_user_id_test",
}


def test_all_required_fields_present():
    s = load_settings(BASE_ENV)
    assert s.FEISHU_APP_ID == "app_id_test"
    assert s.FEISHU_APP_SECRET == "app_secret_test"
    assert s.FEISHU_ENCRYPT_KEY == "encrypt_key_test"
    assert s.FEISHU_ADMIN_USER_ID == "admin_user_id_test"


@pytest.mark.parametrize("missing_key", [
    "FEISHU_APP_ID",
    "FEISHU_APP_SECRET",
    "FEISHU_ENCRYPT_KEY",
    "FEISHU_ADMIN_USER_ID",
])
def test_missing_required_field_raises_value_error(missing_key):
    env = {k: v for k, v in BASE_ENV.items() if k != missing_key}
    with pytest.raises(ValueError):
        load_settings(env)


def test_allowed_user_ids_parsed_from_comma_separated():
    env = {**BASE_ENV, "ALLOWED_USER_IDS": "ou_xxx1,ou_xxx2"}
    s = load_settings(env)
    assert s.ALLOWED_USER_IDS == {"ou_xxx1", "ou_xxx2"}


def test_allowed_user_ids_empty_string_gives_empty_set():
    env = {**BASE_ENV, "ALLOWED_USER_IDS": ""}
    s = load_settings(env)
    assert s.ALLOWED_USER_IDS == set()


def test_port_default_is_8000():
    s = load_settings(BASE_ENV)
    assert s.PORT == 8000


def test_port_parsed_as_int():
    env = {**BASE_ENV, "PORT": "9000"}
    s = load_settings(env)
    assert s.PORT == 9000
    assert isinstance(s.PORT, int)
