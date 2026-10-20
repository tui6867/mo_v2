from types import SimpleNamespace
from unittest.mock import Mock

from streamlit.testing.v1 import AppTest

from outreach import ui
from outreach.services.config import Config
from tests.test_auth_config_sql import ENV


def test_ui_missing_configuration_fails_closed(monkeypatch):
    monkeypatch.setattr(ui, "load_settings", lambda: {})
    for key in ENV:
        monkeypatch.delenv(key, raising=False)
    app = AppTest.from_string("from outreach.ui import run\nrun()", default_timeout=30)
    app.run()
    assert not app.exception
    assert "Missing configuration" in app.error[0].value
    assert not app.button


def test_authenticated_ui_exact_review_uses_mock_only(monkeypatch):
    monkeypatch.setattr(ui, "load_settings", lambda: {})
    config = Config.load(ENV)
    monkeypatch.setattr(Config, "load", classmethod(lambda cls, env=None: config))
    store = Mock()
    store.identity.return_value = SimpleNamespace(id="synthetic-uuid", email="user@example.com")
    store.access.return_value = {
        "is_admin": False,
        "remaining": 300,
        "daily_limit": 300,
        "plan": "plan_1",
    }
    store.suppression.return_value = set()
    store.action.return_value = []
    monkeypatch.setattr(ui, "get_api", lambda *_, **__: store)
    app = AppTest.from_string("from outreach.ui import run\nrun()", default_timeout=30)
    app.session_state["auth_token"] = "synthetic-token"
    app.run()
    fields = {
        "Company": "Synthetic Co",
        "Job title": "Engineer",
        "Job URL": "https://example.com/job",
        "Your name": "Test User",
    }
    for field in app.text_input:
        if field.label in fields:
            field.set_value(fields[field.label])
    app.text_area[0].set_value("Synthetic Person <person@example.com>")
    app.run()
    assert not app.exception
    text = "\n".join(element.value for element in app.text)
    assert "Actual From: sender@example.com" in text
    assert "Actual Reply-To: user@example.com" in text
    assert "To: user@example.com" in text
    assert "person@example.com" in text
    assert "Hello Synthetic" in app.code[0].value
    assert any("reviewed every exact message" in checkbox.label for checkbox in app.checkbox)


def test_login_uses_magic_link_mock_without_public_product_access(monkeypatch):
    monkeypatch.setattr(ui, "load_settings", lambda: {})
    config = Config.load(ENV)
    monkeypatch.setattr(Config, "load", classmethod(lambda cls, env=None: config))
    store = Mock()
    monkeypatch.setattr(ui, "get_api", lambda *_, **__: store)
    app = AppTest.from_string("from outreach.ui import run\nrun()", default_timeout=30)
    app.run()
    app.text_input[0].set_value("synthetic@example.com")
    app.button[0].click().run()
    assert not app.exception
    store.magic_link.assert_called_once_with("synthetic@example.com")
    store.access.assert_not_called()
    store.action.assert_not_called()
