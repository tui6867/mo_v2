"""Opt-in real PostgreSQL tests, never a remote Supabase project.

Set MAIL_RUN_DB_TESTS=1 after Docker Desktop starts. A disposable, network-isolated
Postgres 17 container is created without host ports or durable volumes. Auth tables
and verified JWT claims are minimal fixtures: this verifies SQL/roles/concurrency,
not the hosted GoTrue/PostgREST services or actual email authentication.
"""

import hashlib
import hmac
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

from outreach.domain.pilot import pilot_batch

pytestmark = pytest.mark.skipif(
    os.environ.get("MAIL_RUN_DB_TESTS") != "1",
    reason="Opt-in isolated Docker PostgreSQL test; requires running Docker",
)
SECRET = "synthetic-test-key-" + "s" * 64
OWNER, OTHER, SESSION, OTHER_SESSION = (str(uuid4()) for _ in range(4))


def literal(value):
    return "'" + value.replace("'", "''") + "'"


class Database:
    def __init__(self, container):
        self.container = container

    def sql(self, sql, check=True):
        result = subprocess.run(
            [
                "docker",
                "exec",
                "-i",
                self.container,
                "psql",
                "-U",
                "postgres",
                "-d",
                "postgres",
                "-XAt",
                "-v",
                "ON_ERROR_STOP=1",
            ],
            input=sql,
            text=True,
            capture_output=True,
            timeout=30,
        )
        if check:
            assert result.returncode == 0, result.stderr
        return result

    def as_user(self, sql, owner=OWNER, session=SESSION, role="authenticated", check=True):
        claims = json.dumps({"sub": owner, "session_id": session, "role": role})
        return self.sql(
            f"begin; set local role {role}; select set_config('request.jwt.claims',{literal(claims)},true); {sql}; commit;",
            check,
        )

    def command(
        self,
        operation,
        batch_id=None,
        owner=OWNER,
        session=SESSION,
        signature=None,
        check=True,
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
            ensure_ascii=False,
            separators=(",", ":"),
        )
        signature = (
            signature or hmac.new(SECRET.encode(), command.encode(), hashlib.sha256).hexdigest()
        )
        result = self.as_user(
            f"select public.outreach_mail_action({literal(command)},{literal(signature)})",
            owner,
            session,
            check=check,
        )
        if not check:
            return result
        value = result.stdout.strip().splitlines()[-2]
        return json.loads(value) if value else None  # psql renders SQL NULL as an empty field.

    def start(self, subject="SQL pilot", **kwargs):
        batch_id = str(uuid4())
        batch = pilot_batch(
            "alice@gmail.com", "recipient@example.com", subject, "Synthetic body", False
        )
        result = self.command(
            "start",
            batch_id,
            manifest=batch.manifest(),
            content_hash=batch.digest,
            global_hourly=5,
            global_daily=10,
            **kwargs,
        )
        return batch_id, batch, result


@pytest.fixture(scope="module")
def postgres():
    run = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--network",
            "none",
            "--label",
            "mo-v2-disposable-test=true",
            "-e",
            "POSTGRES_HOST_AUTH_METHOD=trust",
            "postgres:17-alpine",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert run.returncode == 0, (
        "Docker unavailable. Start Docker Desktop; do not retry login or touch the existing relay."
    )
    container = run.stdout.strip()
    db = Database(container)
    try:
        for _ in range(40):
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "postgres"],
                capture_output=True,
                timeout=5,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.25)
        else:
            pytest.fail("Disposable PostgreSQL did not start within 10 seconds")
        db.sql("""
          create role anon nologin;
          create role authenticated nologin;
          create schema auth;
          create table auth.users(id uuid primary key,email text,email_confirmed_at timestamptz);
          create table auth.sessions(id uuid primary key,user_id uuid references auth.users(id));
          create function auth.jwt() returns jsonb language sql stable as $$ select current_setting('request.jwt.claims',true)::jsonb $$;
          create function auth.uid() returns uuid language sql stable as $$ select (auth.jwt()->>'sub')::uuid $$;
          grant usage on schema auth to authenticated,anon;
          grant execute on function auth.jwt(),auth.uid() to authenticated,anon;
        """)
        for path in sorted(Path("supabase/migrations").glob("*.sql")):
            db.sql(path.read_text())
        yield db
    finally:
        # Only this fixture's exact returned container ID; never queues/volumes elsewhere.
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=20)


@pytest.fixture
def db(postgres):
    postgres.sql(f"""
      truncate outreach.audit_events,outreach.recipient_attempts,outreach.quota_reservations,
        outreach.outreach_batches,outreach.suppression_entries,outreach.invitations,outreach.users,
        auth.sessions,auth.users restart identity cascade;
      insert into auth.users values ('{OWNER}','alice@gmail.com',now()),('{OTHER}','bob@gmail.com',now());
      insert into auth.sessions values ('{SESSION}','{OWNER}'),('{OTHER_SESSION}','{OTHER}');
      insert into outreach.users(id,email,is_admin) values ('{OWNER}','alice@gmail.com',true),('{OTHER}','bob@gmail.com',false);
      update outreach.settings set batch_limit=1,global_hourly_limit=5,global_daily_limit=10,
        real_sends_enabled=true,sender_email='legacy@example.com',sender_domain_verified=true;
      update outreach.mail_settings set signing_secret={literal(SECRET)},test_recipient='recipient@example.com',
        live_enabled=true,capture_enabled=true,hourly_limit=5,daily_limit=10;
    """)
    return postgres


def test_real_roles_private_tables_signatures_and_sessions(db):
    assert db.command("check") is True
    assert db.as_user("select * from outreach.mail_settings", check=False).returncode != 0
    assert db.as_user("select public.outreach_access()", role="anon", check=False).returncode != 0
    assert db.command("check", signature="0" * 64, check=False).returncode != 0
    db.sql(f"delete from auth.sessions where id='{SESSION}'")
    assert db.command("check", check=False).returncode != 0


def test_real_history_is_owner_scoped_and_excludes_legacy_records(db):
    assert db.command("list") == []
    own_id, _, _ = db.start(subject="Owner history")
    other_id = str(uuid4())
    other = pilot_batch("bob@gmail.com", "recipient@example.com", "Other history", "Body")
    db.command(
        "start",
        other_id,
        owner=OTHER,
        session=OTHER_SESSION,
        manifest=other.manifest(),
        content_hash=other.digest,
        global_hourly=5,
        global_daily=10,
    )
    # Historical project-SMTP records have no pilot policy and must not leak into this list.
    db.sql(f"""
      insert into outreach.outreach_batches(id,owner_id,content_hash,manifest,test_mode)
      values('{uuid4()}','{OWNER}','{"f" * 64}','{{}}',true);
    """)
    own = db.command("list")
    assert [item["id"] for item in own] == [own_id]
    assert own[0]["subject"] == "Owner history"
    assert set(own[0]) == {"id", "status", "test_mode", "created_at", "subject"}
    assert own[0]["status"] == "started" and own[0]["test_mode"] is False
    assert [item["id"] for item in db.command("list", owner=OTHER, session=OTHER_SESSION)] == [
        other_id
    ]


def test_real_history_returns_only_latest_fifty(db):
    db.sql(f"""
      insert into outreach.outreach_batches(id,owner_id,content_hash,manifest,test_mode,created_at)
      select gen_random_uuid(),'{OWNER}',lpad(i::text,64,'0'),
        jsonb_build_object('transport_policy','user_capture_v1','messages',
          jsonb_build_array(jsonb_build_object('subject','Subject '||i))),
        true,now()-(55-i)*interval '1 second'
      from generate_series(1,55) as i;
    """)
    history = db.command("list")
    assert len(history) == 50
    assert [item["subject"] for item in history] == [f"Subject {i}" for i in range(55, 5, -1)]


def test_real_claim_race_duplicate_start_and_browser_forgery(db):
    batch_id, batch, _ = db.start()
    assert (
        db.command(
            "start",
            batch_id,
            manifest=batch.manifest(),
            content_hash=batch.digest,
            global_hourly=5,
            global_daily=10,
        )["id"]
        == batch_id
    )
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda _: db.command(
                    "claim", batch_id, content_hash=batch.digest, expected_ordinal=0, check=False
                ),
                range(2),
            )
        )
    assert sum(r.returncode == 0 for r in results) == 1
    assert (
        db.as_user(
            f"select public.outreach_action('finish','{batch_id}','{{}}')", check=False
        ).returncode
        != 0
    )
    assert (
        db.as_user(
            f"select outreach.project_action_v1('finish','{batch_id}','{{}}')", check=False
        ).returncode
        != 0
    )
    assert (
        db.command("log", batch_id, owner=OTHER, session=OTHER_SESSION, check=False).returncode != 0
    )


def test_real_shared_quota_race(db):
    db.sql("update outreach.mail_settings set hourly_limit=1")
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(lambda i: db.start(subject=f"Quota race {i}", check=False)[2], range(2))
        )
    assert sum(r.returncode == 0 for r in results) == 1


def test_real_changed_sender_suppression_revocation_and_claim_rechecks(db):
    batch_id, batch, _ = db.start()
    db.sql(
        f"insert into outreach.suppression_entries(owner_id,email) values('{OWNER}','recipient@example.com')"
    )
    assert (
        db.command(
            "claim", batch_id, content_hash=batch.digest, expected_ordinal=0, check=False
        ).returncode
        != 0
    )
    db.sql("delete from outreach.suppression_entries")
    db.sql(f"update auth.users set email='changed@gmail.com' where id='{OWNER}'")
    assert (
        db.command(
            "claim", batch_id, content_hash=batch.digest, expected_ordinal=0, check=False
        ).returncode
        != 0
    )
    db.sql(
        f"update auth.users set email='alice@gmail.com' where id='{OWNER}'; update outreach.users set active=false where id='{OWNER}'"
    )
    assert db.command("log", batch_id, check=False).returncode != 0


def test_real_finish_unknown_recovery_and_holds(db):
    batch_id, batch, _ = db.start()
    claimed = db.command("claim", batch_id, content_hash=batch.digest, expected_ordinal=0)
    assert (
        db.command(
            "finish", batch_id, ordinal=0, claim_token=str(uuid4()), state="accepted", check=False
        ).returncode
        != 0
    )
    assert db.command("recover", batch_id, check=False).returncode != 0
    db.sql(
        f"update outreach.recipient_attempts set updated_at=now()-interval '6 minutes' where batch_id='{batch_id}'"
    )
    assert db.command("recover", batch_id) is True
    assert db.command("log", batch_id)[0]["state"] == "unknown"
    assert db.command("claim", batch_id, content_hash=batch.digest, expected_ordinal=0) is None
    assert (
        db.sql(
            f"select held from outreach.quota_reservations where batch_id='{batch_id}'"
        ).stdout.strip()
        == "1"
    )
    assert (
        db.command(
            "finish",
            batch_id,
            ordinal=0,
            claim_token=claimed["claim_token"],
            state="accepted",
            check=False,
        ).returncode
        != 0
    )


def test_real_invitation_single_use_and_legacy_mode(db):
    secret_hash = hashlib.sha256(b"synthetic-invitation").hexdigest()
    db.as_user(
        f"select public.issue_invitation('bob@gmail.com','{secret_hash}',now()+interval '1 hour')"
    )
    db.as_user(f"select public.redeem_invitation('{secret_hash}')", OTHER, OTHER_SESSION)
    assert (
        db.as_user(
            f"select public.redeem_invitation('{secret_hash}')", OTHER, OTHER_SESSION, check=False
        ).returncode
        != 0
    )
    # Original fake self-recipient behavior and manifest format still work.
    batch = pilot_batch("legacy@example.com", "alice@gmail.com", "Legacy", "Body", True).manifest()
    del batch["transport_policy"]
    batch["reply_to"] = "alice@gmail.com"
    payload = json.dumps(
        {
            "manifest": batch,
            "content_hash": "f" * 64,
            "batch_limit": 1,
            "global_hourly": 5,
            "global_daily": 10,
        }
    )
    batch_id = str(uuid4())
    assert (
        db.as_user(
            f"select public.outreach_action('start','{batch_id}',{literal(payload)}::jsonb)"
        ).returncode
        == 0
    )


@pytest.mark.parametrize("state", ["accepted", "failed"])
def test_real_terminal_outcomes_release_hold_and_cannot_resubmit(db, state):
    batch_id, batch, _ = db.start()
    claim = db.command("claim", batch_id, content_hash=batch.digest, expected_ordinal=0)
    assert (
        db.command(
            "finish",
            batch_id,
            ordinal=0,
            claim_token=claim["claim_token"],
            state=state,
            detail="Synthetic test",
        )
        is True
    )
    assert db.command("claim", batch_id, content_hash=batch.digest, expected_ordinal=0) is None
    assert (
        db.sql(
            f"select held from outreach.quota_reservations where batch_id='{batch_id}'"
        ).stdout.strip()
        == "0"
    )
    assert db.command("log", batch_id)[0]["state"] == state


def test_real_pilot_rejects_forged_sender_recipient_and_uninvited_users(db):
    batch = pilot_batch(
        "alice@gmail.com", "recipient@example.com", "Invalid sender test", "Body"
    ).manifest()
    for changed in (
        dict(batch, sender="bob@gmail.com"),
        dict(batch, reply_to="bob@gmail.com"),
        dict(batch, messages=[dict(batch["messages"][0], to="other@example.com")]),
    ):
        assert (
            db.command(
                "start",
                str(uuid4()),
                manifest=changed,
                content_hash="d" * 64,
                global_hourly=5,
                global_daily=10,
                check=False,
            ).returncode
            != 0
        )
    db.sql(f"delete from outreach.users where id='{OTHER}'")
    assert db.command("check", owner=OTHER, session=OTHER_SESSION, check=False).returncode != 0
    db.sql(f"update auth.users set email_confirmed_at=null where id='{OWNER}'")
    assert db.command("check", check=False).returncode != 0
