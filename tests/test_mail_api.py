import base64
import hashlib
import hmac
import json
import smtplib
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pglast import parse_sql

from outreach.api.app import create_app
from outreach.api.config import Settings, is_public_key
from outreach.api.store import Blocked, MailStore, Principal
from outreach.api.transport import CaptureTransport, GmailTransport
from outreach.api.vault import Vault
from outreach.domain.outcomes import Outcome, State
from outreach.domain.pilot import pilot_batch

SETTINGS = Settings(
    "https://gnmimpoeqxeczjhvzrrx.supabase.co",
    "sb_publishable_synthetic",
    "https://localhost:8443",
    "s" * 64,
    "recipient@example.com",
)
ALICE = Principal(str(uuid4()), "alice@gmail.com", str(uuid4()))
BOB = Principal(str(uuid4()), "bob@gmail.com", str(uuid4()))


class Backend:
    """API orchestration fake; NOT evidence of PostgreSQL RLS/locking correctness."""

    def __init__(self):
        self.rows, self.revoked, self.fail_finish = {}, set(), False
        self.operations = []

    def factory(self, token):
        outer = self

        class Store:
            def identity(self):
                if token not in ("alice", "bob"):
                    raise Blocked(status=401)
                self.principal = ALICE if token == "alice" else BOB
                return self.principal

            def access(self):
                if token in outer.revoked:
                    raise Blocked()
                return {"remaining": 10}

            def command(self, principal, op, batch_id=None, **payload):
                self.access()
                outer.operations.append(op)
                if op == "check":
                    return True
                if op == "list":
                    return [
                        {"id": k, "status": v["state"]}
                        for k, v in outer.rows.items()
                        if v["owner"] == principal.id
                    ]
                if op == "start":
                    outer.rows.setdefault(
                        batch_id, {"state": "not_attempted", "owner": principal.id}
                    )
                    return {"id": batch_id}
                row = outer.rows.get(batch_id)
                if not row or row["owner"] != principal.id:
                    raise Blocked()
                if op == "claim":
                    if row["state"] == "submitting":
                        raise Blocked("Submission already in progress")
                    if row["state"] != "not_attempted":
                        return None
                    row["state"] = "submitting"
                    return {"claim_token": "synthetic-claim"}
                if op == "finish":
                    if outer.fail_finish:
                        raise Blocked(status=503)
                    row.update(state=payload["state"], detail=payload["detail"])
                    return True
                if op == "log":
                    return [{"state": row["state"], "detail": row.get("detail", "")}]
                raise AssertionError(op)

        return Store()


class Transport:
    def __init__(self):
        self.calls, self.verifications = [], []
        self.reject = False
        self.outcome = Outcome(State.ACCEPTED, "Synthetic acceptance, not delivery")

    def verify(self, email, password):
        self.verifications.append(email)
        if self.reject:
            raise Blocked("Wrong credentials", 422)

    def submit(self, connection, batch):
        self.calls.append(batch)
        return self.outcome


@pytest.fixture
def setup():
    backend, transport, vault = Backend(), Transport(), Vault()
    app = create_app(SETTINGS, vault=vault, transport=transport, store_factory=backend.factory)
    with TestClient(
        app,
        base_url=SETTINGS.origin,
        headers={"Origin": SETTINGS.origin, "Authorization": "Bearer alice"},
    ) as client:
        yield client, backend, transport, vault


def reviewed(client):
    connection = client.post("/api/connection", json={}).json()
    draft = {
        "connection_id": connection["id"],
        "recipient": SETTINGS.recipient,
        "subject": "Pilot test",
        "body": "Only a synthetic test.",
    }
    response = client.post("/api/preview", json=draft)
    assert response.status_code == 200
    review = response.json()
    return dict(draft, approval=review["approval"], expires_at=review["expires_at"], confirmed=True)


def test_authentication_revocation_and_https_boundary(setup):
    client, backend, _, _ = setup
    assert client.get("/api/health").status_code == 200
    assert "recipient" not in client.get("/api/config").json()
    assert client.get("/api/me", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/me", headers={"Authorization": "Bearer unknown"}).status_code == 401
    backend.revoked.add("alice")
    assert client.get("/api/me").status_code == 403
    assert (
        client.post(
            "/api/connection", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )


def test_capture_flow_duplicate_clicks_and_server_sender(setup):
    client, backend, transport, _ = setup
    payload = reviewed(client)
    first = client.post("/api/send", json=payload)
    assert first.status_code == 200
    assert client.post("/api/send", json=payload).status_code == 200
    assert len(transport.calls) == 1
    batch = transport.calls[0]
    assert batch.sender == batch.reply_to == ALICE.email
    assert batch.manifest()["transport_policy"] == "user_capture_v1"
    assert backend.operations.index("claim") < backend.operations.index("finish")
    assert "s" * 64 not in first.text
    assert client.post("/api/preview", json=dict(payload, sender=BOB.email)).status_code == 422


@pytest.mark.parametrize(
    "change",
    [
        {"subject": "Changed"},
        {"body": "Changed"},
        {"confirmed": False},
        {"expires_at": 0},
        {"approval": "0" * 64},
        {"recipient": "other@example.com"},
    ],
)
def test_approval_tampering_blocks_smtp(setup, change):
    client, _, transport, _ = setup
    payload = reviewed(client)
    assert client.post("/api/send", json=dict(payload, **change)).status_code in (409, 422)
    assert not transport.calls


def test_connection_cross_user_cross_session_expiry_disconnect_restart(setup):
    client, _, transport, vault = setup
    payload = reviewed(client)
    assert (
        client.post("/api/send", json=payload, headers={"Authorization": "Bearer bob"}).status_code
        == 409
    )
    other_session = replace(ALICE, session=str(uuid4()))
    with pytest.raises(Blocked):
        vault.get(other_session, payload["connection_id"])
    item = vault.get(ALICE, payload["connection_id"])
    item.touched -= 1801
    assert client.post("/api/send", json=payload).status_code == 409
    payload = reviewed(client)
    client.delete("/api/connection")
    assert client.post("/api/send", json=payload).status_code == 409
    payload = reviewed(client)
    vault.clear()  # Simulates process restart; durable intent data is separate.
    assert client.post("/api/send", json=payload).status_code == 409
    assert not transport.calls


def test_revocation_after_preview_blocks_send_and_owner_status(setup):
    client, backend, transport, _ = setup
    payload = reviewed(client)
    backend.revoked.add("alice")
    assert client.post("/api/send", json=payload).status_code == 403
    assert not transport.calls
    backend.revoked.clear()
    result = client.post("/api/send", json=payload).json()
    assert (
        client.get(
            "/api/messages/" + result["id"], headers={"Authorization": "Bearer bob"}
        ).status_code
        == 403
    )


def test_unknown_never_retried_and_failed_finalization(setup):
    client, backend, transport, _ = setup
    transport.outcome = Outcome(State.UNKNOWN, "Connection lost during DATA")
    payload = reviewed(client)
    assert client.post("/api/send", json=payload).json()["attempts"][0]["state"] == "unknown"
    client.post("/api/send", json=payload)
    assert len(transport.calls) == 1
    backend.rows.clear()
    backend.fail_finish = True
    response = client.post("/api/send", json=payload)
    assert response.status_code == 202 and "Do not resend" in response.text
    client.post("/api/send", json=payload)
    assert len(transport.calls) == 2


def test_capture_rejects_password_and_validation_never_echoes_inputs(setup):
    client, _, _, _ = setup
    secret = "synthetic-secret-value"
    response = client.post("/api/connection", json={"app_password": secret})
    assert response.status_code == 422 and secret not in response.text
    response = client.post("/api/connection", json={"app_password": {"bad": secret}})
    assert response.status_code == 422 and secret not in response.text
    assert client.post("/api/connection", content="x" * 65537).status_code == 413


def test_live_wrong_credentials_throttle_and_memory_only():
    backend, transport, vault = Backend(), Transport(), Vault()
    settings = replace(SETTINGS, transport="gmail", real_sends=True)
    transport.reject = True
    with TestClient(
        create_app(settings, vault=vault, transport=transport, store_factory=backend.factory),
        base_url=settings.origin,
        headers={"Origin": settings.origin, "Authorization": "Bearer alice"},
    ) as client:
        for _ in range(5):
            assert (
                client.post(
                    "/api/connection", json={"app_password": "abcd efgh ijkl mnop"}
                ).status_code
                == 422
            )
        assert (
            client.post("/api/connection", json={"app_password": "abcdefghijklmnop"}).status_code
            == 429
        )
        assert not vault.items and not transport.calls


def test_hmac_commands_and_verified_identity_use_only_user_jwt():
    requests = []
    claims = (
        base64.urlsafe_b64encode(
            json.dumps({"sub": ALICE.id, "session_id": ALICE.session}).encode()
        )
        .decode()
        .rstrip("=")
    )
    token = "header." + claims + ".signature"

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"id": ALICE.id, "email": ALICE.email, "email_confirmed_at": "2026-10-20"}
            if request.url.path.endswith("/user")
            else True,
        )

    with httpx.Client(transport=httpx.MockTransport(handle)) as http:
        store = MailStore(SETTINGS, token, http)
        assert store.identity() == ALICE
        store.command(ALICE, "check")
    payload = json.loads(requests[-1].content)
    assert (
        payload["signature"]
        == hmac.new(
            SETTINGS.signing_secret.encode(), payload["command"].encode(), hashlib.sha256
        ).hexdigest()
    )
    assert all(r.headers["Authorization"] == "Bearer " + token for r in requests)
    assert SETTINGS.signing_secret not in payload["command"]


def test_gmail_verification_tls_fixed_host_no_mail(monkeypatch):
    calls = []

    class SMTP:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self, context):
            assert context.check_hostname
            calls.append("tls")

        def login(self, email, password):
            calls.append("login")

        def close(self):
            calls.append("close")

    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    GmailTransport().verify(ALICE.email, "synthetic")
    assert calls == [("smtp.gmail.com", 587, 20), "ehlo", "tls", "ehlo", "login", "close"]


def test_capture_has_no_arbitrary_host_and_never_authenticates(monkeypatch):
    class SMTP:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("postfix", 587)

        def sendmail(self, sender, recipients, wire):
            assert recipients == [SETTINGS.recipient]
            assert b"Date:" in wire and b"Message-ID:" in wire

        def close(self):
            pass

    monkeypatch.setattr(smtplib, "SMTP", SMTP)
    vault = Vault()
    connection = vault.get(ALICE, vault.add(ALICE, "")["id"])
    outcome = CaptureTransport().submit(
        connection, pilot_batch(ALICE.email, SETTINGS.recipient, "Test", "Body", True)
    )
    assert outcome.state == State.ACCEPTED
    connection.password = "should-never-be-here"
    with pytest.raises(Blocked):
        CaptureTransport().submit(
            connection, pilot_batch(ALICE.email, SETTINGS.recipient, "Test", "Body", True)
        )


def test_config_project_guard_and_sql_parse_not_execution():
    env = {
        "MAIL_SUPABASE_URL": SETTINGS.supabase_url,
        "MAIL_SUPABASE_PUBLISHABLE_KEY": SETTINGS.anon_key,
        "MAIL_SIGNING_SECRET": SETTINGS.signing_secret,
        "MAIL_TEST_RECIPIENT": SETTINGS.recipient,
    }
    assert Settings.load(env).transport == "capture"
    for changed in (
        {"MAIL_SUPABASE_URL": "https://iaubupnvesznnxxerimx.supabase.co"},
        {"MAIL_ORIGIN": "http://localhost:8443"},
        {"MAIL_SIGNING_SECRET": ""},
        {"MAIL_SUPABASE_PUBLISHABLE_KEY": "sb_secret_synthetic"},
        {"MAIL_HOURLY_LIMIT": "6"},
    ):
        with pytest.raises(ValueError):
            Settings.load(dict(env, **changed))
    sql = Path("supabase/migrations/20261020223515_session_mail_pilot.sql").read_text()
    assert parse_sql(sql)
    assert sql.count("perform outreach.mail_eligibility(actor,manifest)") == 1
    assert "if op in ('start','claim')" in sql
    assert "pg_advisory_xact_lock(610110001)" in sql


def test_vault_absolute_lifetime_lock_and_idle_cleanup():
    now = [10000.0]
    vault = Vault(clock=lambda: now[0])
    connection_id = vault.add(ALICE, "synthetic-password")["id"]
    with vault.use(ALICE, connection_id):
        with pytest.raises(Blocked, match="already in progress"):
            with vault.use(ALICE, connection_id):
                pytest.fail("Second concurrent operation entered")
    for _ in range(4):
        now[0] += 1700
        with vault.use(ALICE, connection_id):
            pass
    now[0] += 401
    with pytest.raises(Blocked, match="expired"):
        vault.get(ALICE, connection_id)
    connection_id = vault.add(ALICE, "synthetic-password")["id"]
    now[0] += 1801
    vault.prune()
    assert not vault.items


def test_legacy_privileged_key_is_never_mistaken_for_browser_key():
    def key(role):
        claims = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode()
        return "header." + claims + ".signature"

    assert is_public_key(key("anon"))
    assert not is_public_key(key("service_role"))
    assert not is_public_key("sb_secret_synthetic")


def test_non_ascii_approval_and_subject_controls_are_rejected(setup):
    client, _, transport, _ = setup
    payload = reviewed(client)
    assert client.post("/api/send", json=dict(payload, approval="é" * 64)).status_code == 422
    with pytest.raises(ValueError, match="Subject"):
        pilot_batch(ALICE.email, SETTINGS.recipient, "bad\x01subject", "Body")
    assert not transport.calls
