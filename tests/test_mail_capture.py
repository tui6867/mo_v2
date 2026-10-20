"""Opt-in smoke tests against the synthetic Compose verification stack.

Start ONLY the documented compose.verify.yaml stack first, then set
MAIL_RUN_CAPTURE_TESTS=1. No app credentials, Auth login or external emails.
"""

import json
import os
import ssl
import subprocess
import time
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("MAIL_RUN_CAPTURE_TESTS") != "1",
    reason="Opt-in synthetic Compose capture smoke test",
)
PROJECT = "mo-v2-mail-pilot-verification"
COMPOSE = [
    "docker",
    "compose",
    "-p",
    PROJECT,
    "-f",
    "infra/compose.yaml",
    "-f",
    "infra/compose.verify.yaml",
]


def command(args, source=None):
    result = subprocess.run(args, input=source, text=True, capture_output=True, timeout=40)
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture(scope="module")
def https_client():
    public_root = command(
        COMPOSE + ["exec", "-T", "web", "cat", "/data/caddy/pki/authorities/local/root.crt"]
    )
    context = ssl.create_default_context(cadata=public_root)
    with httpx.Client(base_url="https://localhost:8443", verify=context, timeout=10) as client:
        config = client.get("/api/config").json()
        # Never run transport tests against operator-configured real credentials.
        assert config["transport"] == "capture" and config["live_enabled"] is False
        assert config["publishable_key"] == "sb_publishable_synthetic_not_a_valid_key"
        yield client


def test_real_https_proxy_frontend_and_anonymous_auth_boundary(https_client):
    response = https_client.get("/")
    assert response.status_code == 200 and '<div id="root">' in response.text
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert https_client.get("/api/health").json()["status"] == "ok"
    assert https_client.get("/api/me").status_code == 401
    assert https_client.post("/api/connection", json={}).status_code == 403
    assert (
        https_client.post(
            "/api/connection", json={}, headers={"Origin": "https://localhost:8443"}
        ).status_code
        == 401
    )


def test_real_postfix_to_mailpit_capture_and_network_isolation(https_client):
    assert (
        command(
            ["docker", "network", "inspect", PROJECT + "_capture", "--format", "{{.Internal}}"]
        ).strip()
        == "true"
    )
    for service in ("postfix", "mailpit"):
        networks = json.loads(
            command(
                [
                    "docker",
                    "inspect",
                    f"{PROJECT}-{service}-1",
                    "--format",
                    "{{json .NetworkSettings.Networks}}\n",
                ]
            )
        )
        assert list(networks) == [PROJECT + "_capture"]
    subject = "Synthetic capture smoke " + uuid4().hex
    source = f"""
from types import SimpleNamespace
from outreach.domain.pilot import pilot_batch
from outreach.api.transport import CaptureTransport
from outreach.domain.outcomes import State
batch = pilot_batch('synthetic@gmail.com','recipient@example.com',{subject!r},'Synthetic capture only. No external delivery.',True)
outcome = CaptureTransport().submit(SimpleNamespace(email=batch.sender,password=''),batch)
assert outcome.state == State.ACCEPTED, outcome.detail
print('Private relay accepted synthetic message')
"""
    command(COMPOSE + ["exec", "-T", "api", "python", "-"], source)
    # Postfix acceptance precedes capture; wait a bounded ten seconds for handoff.
    with httpx.Client(base_url="http://localhost:8026", timeout=5) as client:
        for _ in range(20):
            messages = client.get("/api/v1/messages").json()["messages"]
            match = next((m for m in messages if m["Subject"] == subject), None)
            if match:
                break
            time.sleep(0.5)
        else:
            pytest.fail(
                "Postfix accepted, but Mailpit did not capture within ten seconds; inspect private queue"
            )
        detail = client.get("/api/v1/message/" + match["ID"]).json()
        assert detail["From"]["Address"] == "synthetic@gmail.com"
        assert detail["To"][0]["Address"] == "recipient@example.com"
        assert "Synthetic capture only" in detail["Text"]
