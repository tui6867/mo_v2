import ast
import json
import re
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pglast import parse_sql
from pglast.parser import parse_plpgsql_json

from outreach.domain.invitations import Invitation
from outreach.services.config import Config
from outreach.services.supabase import Supabase

ENV = {
    "SUPABASE_URL": "https://synthetic.supabase.co",
    "SUPABASE_ANON_KEY": "synthetic-not-a-key",
    "AUTH_REDIRECT_URL": "https://example.com",
    "SENDER_EMAIL": "sender@example.com",
    "SENDER_DOMAIN_VERIFIED": "true",
    "BATCH_LIMIT": "300",
    "GLOBAL_HOURLY_LIMIT": "1000",
    "GLOBAL_DAILY_LIMIT": "2000",
    "MAX_ATTACHMENT_BYTES": "1000000",
    "MAX_MESSAGE_BYTES": "2000000",
    "MAX_CSV_BYTES": "100000",
}


def test_invitation_constraints():
    now = datetime.now(UTC)
    invitation = Invitation("user@example.com", now + timedelta(days=1))
    invitation.validate_redemption("user@EXAMPLE.COM", now)
    for changed in (
        replace(invitation, expires_at=now),
        replace(invitation, revoked_at=now),
        replace(invitation, redeemed_at=now),
    ):
        with pytest.raises(ValueError):
            changed.validate_redemption("user@example.com", now)
    with pytest.raises(ValueError):
        invitation.validate_redemption("other@example.com", now)


def test_required_config_fails_closed():
    config = Config.load(ENV)
    assert not config.real_sends
    for field in ENV:
        with pytest.raises(ValueError):
            Config.load({k: v for k, v in ENV.items() if k != field})
    for field in ("BATCH_LIMIT", "GLOBAL_HOURLY_LIMIT", "GLOBAL_DAILY_LIMIT"):
        for bad in ("0", "-1", "invalid"):
            with pytest.raises(ValueError):
                Config.load(dict(ENV, **{field: bad}))
    with pytest.raises(ValueError):
        Config.load(dict(ENV, SENDER_DOMAIN_VERIFIED="false"))


def test_supabase_user_jwt_and_hashed_invitation_only():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/auth/v1/user":
            return httpx.Response(
                200,
                json={
                    "id": "00000000-0000-0000-0000-000000000001",
                    "email": "user@example.com",
                    "email_confirmed_at": "2026-10-11T00:00:00Z",
                },
            )
        return httpx.Response(200, json={"is_admin": True})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = Supabase(Config.load(ENV), "synthetic-user-jwt", client)
    assert store.identity().email == "user@example.com"
    store.redeem("synthetic-secret")
    token = store.issue("user@example.com", "2026-10-12T00:00:00Z")
    assert all(r.headers["Authorization"] == "Bearer synthetic-user-jwt" for r in requests)
    assert b"synthetic-secret" not in requests[1].content
    assert token.encode() not in requests[2].content
    assert b"secret_hash" in requests[2].content


def test_unverified_auth_and_raw_auth_errors_not_exposed():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json={"email": "user@example.com"})
        )
    )
    with pytest.raises(ValueError, match="Verify control"):
        Supabase(Config.load(ENV), "token", client).identity()
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _: httpx.Response(401, json={"message": "secret-sensitive"})
        )
    )
    with pytest.raises(ValueError, match="Authentication failed") as error:
        Supabase(Config.load(ENV), "token", client).identity()
    assert "secret-sensitive" not in str(error.value)


def test_magic_link_redirect_parameter_and_no_service_role_or_fake_bearer():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = Supabase(Config.load(ENV), client=client)
    store.magic_link("synthetic@EXAMPLE.com")
    assert requests[0].url.params["redirect_to"] == ENV["AUTH_REDIRECT_URL"]
    assert "Authorization" not in requests[0].headers
    assert json.loads(requests[0].content)["email"] == "synthetic@example.com"


def test_sql_security_and_concurrency_contract_not_integration():
    sql = Path("supabase/migrations/202610110001_invite_outreach.sql").read_text()
    assert "pg_advisory_xact_lock(610110001)" in sql
    assert "for update" in sql and "b.owner_id=auth.uid()" in sql
    assert "unknown" in sql and "interval '5 minutes'" in sql
    assert "email_confirmed_at is not null" in sql and "invited.redeemed_at is not null" in sql
    for table in (
        "users",
        "invitations",
        "outreach_batches",
        "recipient_attempts",
        "quota_reservations",
        "suppression_entries",
        "audit_events",
    ):
        assert f"alter table outreach.{table} enable row level security" in sql
    assert "from public, anon" in sql
    assert "'plan_1', 300" in sql
    assert "at time zone 'UTC'" in sql


def test_postgres_and_plpgsql_syntax_not_execution():
    sql = Path("supabase/migrations/202610110001_invite_outreach.sql").read_text()
    assert len(parse_sql(sql)) == 37
    # pglast has no catalog for the new outreach composite row types. Replacing
    # only declaration types with record permits body syntax validation, not
    # type/catalog resolution, RLS validation or transaction/concurrency proof.
    syntax_only = re.sub(
        r"\b(u|invited|b|settings|r) outreach\.(users|invitations|outreach_batches|settings|recipient_attempts)",
        r"\1 record",
        sql,
    )
    assert len(json.loads(parse_plpgsql_json(syntax_only))) == 4


def test_domain_has_no_ui_network_or_database_imports_and_root_composes_only():
    for path in Path("outreach/domain").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert not any(
                    i.name.split(".")[0] in {"streamlit", "requests", "supabase", "httpx"}
                    for i in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in {
                    "streamlit",
                    "requests",
                    "supabase",
                    "httpx",
                }
    root = Path("app.py").read_text(encoding="utf-8")
    assert "billing" not in root and "patch_streamlit" not in root
    assert len(root.splitlines()) < 20
