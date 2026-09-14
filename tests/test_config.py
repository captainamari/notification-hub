from app.config import Settings


def base_settings(**overrides):
    values = {"api_token": "x" * 32}
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_default_routes_are_stable():
    settings = base_settings()
    assert settings.routes == {
        "default": ["telegram"],
        "ops": ["telegram"],
        "trading": ["telegram"],
        "warning": ["telegram", "email"],
        "critical": ["telegram", "email"],
    }


def test_telegram_url_can_be_built_from_simple_settings():
    settings = base_settings(
        telegram_bot_token="123:abc",
        telegram_chat_ids="10001,@alerts",
    )
    assert settings.provider_urls["telegram"] == "tgram://123:abc/10001/@alerts"


def test_email_url_can_be_built_from_simple_settings():
    settings = base_settings(
        smtp_host="smtp.example.com",
        smtp_username="sender@example.com",
        smtp_password="secret password",
        email_from="sender@example.com",
        email_to="owner@example.com",
    )
    url = settings.provider_urls["email"]
    assert url.startswith("mailtos://sender%40example.com:secret%20password@smtp.example.com:587/")
    assert "owner%40example.com" in url
