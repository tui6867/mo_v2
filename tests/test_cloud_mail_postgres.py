"""Opt-in isolated PostgreSQL security/quota tests for the Cloudflare application."""

import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from tests.test_mail_postgres import OTHER, OTHER_SESSION, OWNER, SECRET, SESSION, literal
from tests.test_mail_postgres import db as db  # Reuse the disposable, network-isolated fixture.
from tests.test_mail_postgres import postgres as postgres
from tests.test_mail_postgres import pytestmark as pytestmark


class Cloud:
    def __init__(self, db):
        self.db = db

    def act(
        self,
        operation,
        batch_id=None,
        owner=OWNER,
        session=SESSION,
        check=True,
        signature=None,
        **payload,
    ):
        command = json.dumps(
            {
                "owner": owner,
                "session": session,
                "expires": int(time.time()) + 60,
                "operation": operation,
                "batch_id": batch_id,
                "payload": payload,
            },
            separators=(",", ":"),
        )
        signature = (
            signature or hmac.new(SECRET.encode(), command.encode(), hashlib.sha256).hexdigest()
        )
        result = self.db.as_user(
            f"select public.cloud_mail_action({literal(command)},{literal(signature)})",
            owner,
            session,
            check=check,
        )
        if not check:
            return result
        value = result.stdout.strip().splitlines()[-2]
        return json.loads(value) if value else None

    def start(self, n=1, label="Cloud test", owner=OWNER, session=SESSION, check=True):
        messages = [
            {
                "email": f"person{i}@example.com",
                "name": f"Person {i}",
                "subject": label,
                "body": "Explicitly approved synthetic content.",
            }
            for i in range(n)
        ]
        return self.act(
            "start",
            str(uuid4()),
            owner=owner,
            session=session,
            check=check,
            messages=messages,
            content_hash=hashlib.sha256(json.dumps(messages).encode()).hexdigest(),
        )

    def claim(self, batch_id, ordinal=0, **kwargs):
        return self.act(
            "claim", batch_id, ordinal=ordinal, message_id=f"<{uuid4()}@gmail.com>", **kwargs
        )


@pytest.fixture
def cloud(db):
    db.sql(f"""
      update outreach.settings set real_sends_enabled=false;
      update outreach.mail_settings set live_enabled=false;
      update outreach.cloud_settings set signing_secret={literal(SECRET)},live_enabled=true,
        debug_enabled=true,batch_limit=5,user_daily_limit=10,global_daily_limit=50;
    """)
    return Cloud(db)


def test_cloud_roles_signatures_sessions_and_owner_isolation(cloud):
    assert cloud.act("me")["approved"] is True
    assert cloud.act("me", signature="0" * 64, check=False).returncode != 0
    assert cloud.act("me", session=OTHER_SESSION, check=False).returncode != 0
    assert cloud.db.as_user("select * from outreach.cloud_settings", check=False).returncode != 0
    assert cloud.db.as_user("select outreach.cloud_usage(auth.uid())", check=False).returncode != 0
    assert (
        cloud.db.as_user(
            "select public.cloud_mail_action('{}','x')", role="anon", check=False
        ).returncode
        != 0
    )
    batch_id = cloud.start()["id"]
    assert (
        cloud.act("get", batch_id, owner=OTHER, session=OTHER_SESSION, check=False).returncode != 0
    )
    assert cloud.act("list", owner=OTHER, session=OTHER_SESSION) == []
    assert [item["id"] for item in cloud.act("list")] == [batch_id]
    cloud.db.sql(f"delete from auth.sessions where id='{SESSION}'")
    assert cloud.act("me", check=False).returncode != 0


def test_cloud_pending_approval_and_revocation_cannot_self_restore(cloud):
    cloud.db.sql(f"delete from outreach.users where id='{OTHER}'")
    assert cloud.act("me", owner=OTHER, session=OTHER_SESSION)["approved"] is False
    cloud.act(
        "request_access",
        owner=OTHER,
        session=OTHER_SESSION,
        full_name="Bob",
        purpose="Permitted personal introductions",
    )
    assert cloud.start(owner=OTHER, session=OTHER_SESSION, check=False).returncode != 0
    assert (
        cloud.act(
            "admin_approve", id=OTHER, owner=OTHER, session=OTHER_SESSION, check=False
        ).returncode
        != 0
    )
    cloud.act("admin_approve", id=OTHER)
    assert cloud.act("me", owner=OTHER, session=OTHER_SESSION)["approved"] is True
    assert cloud.act("me", owner=OTHER, session=OTHER_SESSION)["is_admin"] is False
    batch_id = cloud.start(n=2, owner=OTHER, session=OTHER_SESSION)["id"]
    claim = cloud.claim(batch_id, owner=OTHER, session=OTHER_SESSION)
    cloud.act("admin_revoke", id=OTHER)
    assert cloud.act("me", owner=OTHER, session=OTHER_SESSION)["approved"] is False
    assert (
        cloud.claim(batch_id, ordinal=1, owner=OTHER, session=OTHER_SESSION, check=False).returncode
        != 0
    )
    # Already-claimed outcome can finalize after revocation; queued holds were cancelled.
    cloud.act(
        "finish",
        batch_id,
        owner=OTHER,
        session=OTHER_SESSION,
        ordinal=0,
        claim_token=claim["claim_token"],
        state="accepted",
    )
    assert cloud.db.sql(
        f"select state from outreach.cloud_attempts where batch_id='{batch_id}' order by ordinal"
    ).stdout.strip().splitlines() == ["accepted", "cancelled"]
    cloud.act(
        "request_access",
        owner=OTHER,
        session=OTHER_SESSION,
        full_name="Bob",
        purpose="Another request",
    )
    assert cloud.act("me", owner=OTHER, session=OTHER_SESSION)["approved"] is False
    assert cloud.act("admin_revoke", id=OWNER, check=False).returncode != 0


def test_cloud_atomic_limits_and_duplicate_protection(cloud):
    first = cloud.start(n=5, label="First")
    assert cloud.start(n=5, label="First") == {"id": first["id"], "existing": True}
    assert cloud.act("me")["remaining"] == 5
    second = cloud.start(n=5, label="Second")
    assert cloud.act("me")["remaining"] == 0
    assert cloud.start(label="Over cap", check=False).returncode != 0
    assert cloud.start(n=6, check=False).returncode != 0
    cloud.act("cancel", second["id"])
    assert cloud.act("me")["remaining"] == 5
    cloud.act(
        "admin_update",
        id=OWNER,
        full_name="Alice",
        daily_limit=4,
        admin_notes="Lowered during batch",
    )
    assert cloud.claim(first["id"], check=False).returncode != 0


def test_cloud_global_limit_serializes_racing_users(cloud):
    cloud.db.sql("update outreach.cloud_settings set global_daily_limit=5")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda identity: cloud.start(
                    n=5, label=identity[0], owner=identity[0], session=identity[1], check=False
                ),
                [(OWNER, SESSION), (OTHER, OTHER_SESSION)],
            )
        )
    assert sum(result.returncode == 0 for result in results) == 1
    assert (
        cloud.db.sql(
            "select count(*) from outreach.cloud_attempts where state='pending'"
        ).stdout.strip()
        == "5"
    )


def test_cloud_claim_finish_unknown_and_recovery(cloud):
    batch_id = cloud.start()["id"]
    claim = cloud.claim(batch_id)
    assert cloud.claim(batch_id, check=False).returncode != 0
    assert (
        cloud.act(
            "finish", batch_id, ordinal=0, claim_token=str(uuid4()), state="accepted", check=False
        ).returncode
        != 0
    )
    cloud.db.sql(
        f"update outreach.cloud_attempts set updated_at=now()-interval '6 minutes' where batch_id='{batch_id}'"
    )
    batch = cloud.act("recover", batch_id)
    assert batch["attempts"][0]["state"] == "unknown"
    assert cloud.act("me")["remaining"] == 9
    assert cloud.claim(batch_id) is None  # Terminal and never submitted twice.
    assert (
        cloud.act(
            "finish",
            batch_id,
            ordinal=0,
            claim_token=claim["claim_token"],
            state="accepted",
            check=False,
        ).returncode
        != 0
    )


def test_cloud_kill_switch_suppression_and_header_injection(cloud):
    batch_id = cloud.start()["id"]
    cloud.act("suppress", email="person0@example.com")
    assert cloud.claim(batch_id, check=False).returncode != 0
    assert cloud.start(label="Suppressed", check=False).returncode != 0
    cloud.act("admin_settings", live_enabled=False)
    assert cloud.claim(batch_id, check=False).returncode != 0
    assert cloud.act("get", batch_id)["id"] == batch_id
    assert cloud.act("admin_settings", live_enabled=True, check=False).returncode != 0
    cloud.act("admin_settings", live_enabled=True, policy_ack="permitted_messages_only")
    bad = [
        {
            "name": "Valid",
            "email": "other@example.com",
            "subject": "Hello\nBcc: bad@example.com",
            "body": "Body",
        }
    ]
    assert (
        cloud.act(
            "start", str(uuid4()), messages=bad, content_hash="f" * 64, check=False
        ).returncode
        != 0
    )
    cloud.db.sql("update outreach.mail_settings set live_enabled=true")
    assert cloud.start(label="Parallel old transport", check=False).returncode != 0


def test_cloud_connection_throttle_and_debug_permissions(cloud):
    for _ in range(5):
        cloud.act("connect_attempt")
    assert cloud.act("connect_attempt", check=False).returncode != 0
    assert cloud.act("debug")["session_verified"] is True
    assert cloud.act("debug", owner=OTHER, session=OTHER_SESSION, check=False).returncode != 0
    cloud.act("admin_settings", debug_enabled=False)
    assert cloud.act("debug", check=False).returncode != 0
    assert cloud.act("admin_users", owner=OTHER, session=OTHER_SESSION, check=False).returncode != 0
