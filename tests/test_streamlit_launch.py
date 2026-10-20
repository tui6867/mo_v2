import tomllib
from pathlib import Path
from unittest.mock import Mock

import httpx
import pytest
from pglast import ast as pg_ast
from pglast import parse_sql
from streamlit.testing.v1 import AppTest

from outreach import connections, preflight, ui
from outreach.connections import SupabaseConnection
from outreach.services.config import Config
from outreach.streamlit_settings import SETTING_NAMES, load_settings
from tests.test_auth_config_sql import ENV


def test_streamlit_typed_secrets_and_explicit_environment_override():
    secrets = dict(ENV, BATCH_LIMIT=50, ENABLE_REAL_SENDS=False, SENDER_DOMAIN_VERIFIED=True)
    settings = load_settings(env={}, secrets=secrets)
    config = Config.load(settings)
    assert config.batch_limit == 50 and not config.real_sends
    assert config.sender == "sender@example.com"
    settings = load_settings(
        env={"BATCH_LIMIT": "10", "ENABLE_REAL_SENDS": "false"},
        secrets=dict(secrets, ENABLE_REAL_SENDS=True),
    )
    assert Config.load(settings).batch_limit == 10 and not Config.load(settings).real_sends
    with pytest.raises(ValueError):
        Config.load(load_settings(env={"SUPABASE_URL": ""}, secrets=secrets))
    assert "SUPABASE_SERVICE_ROLE_KEY" not in load_settings(
        env={}, secrets={"SUPABASE_SERVICE_ROLE_KEY": "never-used"}
    )


@pytest.mark.parametrize(
    "value",
    [
        "https://user:secret@example.com/",
        "https://example.com/?token=x",
        "https://example.com/#access_token=x",
    ],
)
def test_auth_redirect_and_api_url_reject_credential_or_callback_confusion(value):
    for key in ("SUPABASE_URL", "AUTH_REDIRECT_URL"):
        with pytest.raises(ValueError):
            Config.load(dict(ENV, **{key: value}))


def test_connection_no_network_at_construction_and_jwt_not_cached(monkeypatch):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"remaining": 300})

    transport = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(connections.httpx, "Client", lambda **_: transport)
    conn = SupabaseConnection("launch-test")
    assert conn.scope() == "session" and not requests
    config = Config.load(ENV)
    first = conn.api(config, "synthetic-user-one")
    second = conn.api(config, "synthetic-user-two")
    first.access()
    second.access()
    first.access()
    assert [r.headers["Authorization"] for r in requests] == [
        "Bearer synthetic-user-one",
        "Bearer synthetic-user-two",
        "Bearer synthetic-user-one",
    ]
    assert "Authorization" not in transport.headers
    assert conn.api(config).token == ""
    conn.close()
    assert transport.is_closed


def test_connection_instances_are_session_scoped_and_reset_closes_transport(monkeypatch):
    factory = Mock(side_effect=[Mock(), Mock()])
    monkeypatch.setattr(connections.httpx, "Client", factory)
    first, second = SupabaseConnection("a"), SupabaseConnection("b")
    assert first._instance is not second._instance
    raw = first._instance
    first.reset()
    raw.close.assert_called_once()
    assert first._raw_instance is None
    second.close()


def test_official_connection_factory_isolates_two_streamlit_sessions(monkeypatch):
    clients = []
    real_client = httpx.Client

    def factory(**kwargs):
        def handler(request):
            return httpx.Response(200, json={"owner": request.headers["Authorization"]})

        client = real_client(transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    monkeypatch.setattr(connections.httpx, "Client", factory)
    source = """
import streamlit as st
from streamlit.runtime.scriptrunner import get_script_run_ctx
from outreach.connections import get_api
from outreach.services.config import Config
from tests.test_auth_config_sql import ENV
# AppTest runners otherwise share the literal "test session id". Distinct
# synthetic context IDs model real browser sessions for the resource cache.
get_script_run_ctx().session_id = st.session_state['synthetic_session']
api = get_api(Config.load(ENV), st.session_state['synthetic_token'])
st.text(api.access()['owner'])
st.text(str(id(api.client)))
"""
    first = AppTest.from_string(source, default_timeout=30)
    second = AppTest.from_string(source, default_timeout=30)
    first.session_state["synthetic_token"] = "first-user"
    second.session_state["synthetic_token"] = "second-user"
    first.session_state["synthetic_session"] = "launch-test-session-one"
    second.session_state["synthetic_session"] = "launch-test-session-two"
    try:
        first.run()
        second.run()
        assert not first.exception and not second.exception
        assert first.text[0].value == "Bearer first-user"
        assert second.text[0].value == "Bearer second-user"
        assert first.text[1].value != second.text[1].value
        first.session_state["synthetic_token"] = "changed-user"
        first.run()
        assert first.text[0].value == "Bearer changed-user"
        second.run()
        assert second.text[0].value == "Bearer second-user"
    finally:
        for client in clients:
            client.close()


def test_cloud_secrets_reach_login_without_network(monkeypatch):
    store = Mock()
    monkeypatch.setattr(ui, "get_api", lambda *_: store)
    monkeypatch.setattr(
        ui,
        "load_settings",
        lambda: load_settings(
            env={},
            secrets=dict(ENV, BATCH_LIMIT=50, ENABLE_REAL_SENDS=False, SENDER_DOMAIN_VERIFIED=True),
        ),
    )
    app = AppTest.from_string("from outreach.ui import run\nrun()", default_timeout=30)
    app.run()
    assert not app.exception and not app.error
    assert app.text_input[0].label == "Invited email"
    store.magic_link.assert_not_called()
    store.action.assert_not_called()


def test_launch_templates_are_safe_toml_and_cloud_uses_uv():
    config = tomllib.loads(Path(".streamlit/config.toml").read_text())
    assert config["server"]["enableXsrfProtection"] and config["server"]["enableCORS"]
    assert config["server"]["maxUploadSize"] == 10
    secrets = tomllib.loads(Path(".streamlit/secrets.toml.example").read_text())
    assert not secrets["ENABLE_REAL_SENDS"] and not secrets["SENDER_DOMAIN_VERIFIED"]
    assert secrets["SUPABASE_ANON_KEY"] == "" and secrets["SMTP_PASSWORD"] == ""
    assert Path("uv.lock").is_file() and not Path("requirements.txt").exists()
    assert ".streamlit/secrets.toml" in Path(".gitignore").read_text()


def test_backend_launch_checks_are_parseable_read_only_selects():
    statements = parse_sql(Path("supabase/launch_checks.sql").read_text())
    assert len(statements) == 8
    assert all(isinstance(item.stmt, pg_ast.SelectStmt) for item in statements)


def test_backend_setup_template_has_fail_closed_guard_and_no_real_activation():
    sql = Path("supabase/launch_setup.example.sql").read_text()
    statements = parse_sql(sql)
    assert len(statements) == 3
    assert "verified_admin_id uuid := null" in sql and "domain_is_verified boolean := false" in sql
    assert sql.index("raise exception 'Fill verified") < sql.index("update outreach.settings")
    assert "email_confirmed_at is not null" in sql
    assert "real_sends_enabled=false" in sql and "not active" in sql


def test_offline_preflight_never_sends_and_redacts_errors(tmp_path, monkeypatch, capsys):
    for key in SETTING_NAMES:
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / "synthetic.toml"
    path.write_text("\n".join(f'{key} = "{value}"' for key, value in ENV.items()), encoding="utf-8")
    assert preflight.main(["--secrets-file", str(path)]) == 0
    assert "NOT verified" in capsys.readouterr().out
    path.write_text(
        'SMTP_PASSWORD = "sensitive-test-value"\nBATCH_LIMIT = "invalid"', encoding="utf-8"
    )
    assert preflight.main(["--secrets-file", str(path)]) == 1
    output = capsys.readouterr().out
    assert "sensitive-test-value" not in output and "invalid" in output


def test_smtp_uses_toml_settings_not_uncontrolled_environment(monkeypatch):
    from outreach.services.smtp import SMTPAdapter
    from tests.test_smtp import SMTP_ENV

    settings = load_settings(env={}, secrets=dict(SMTP_ENV, SMTP_PORT=465, SMTP_TIMEOUT_SECONDS=30))
    monkeypatch.setenv("SMTP_PASSWORD", "different-environment-value")
    adapter = SMTPAdapter(settings)
    assert adapter.port == 465 and adapter.timeout == 30
    assert adapter.password == "synthetic-not-real"
