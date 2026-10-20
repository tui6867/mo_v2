import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx

from outreach.domain.recipients import email_key


class Blocked(Exception):
    def __init__(
        self, detail="Operation blocked; check access and development database setup", status=403
    ):
        self.detail, self.status = detail, status


@dataclass(frozen=True)
class Principal:
    id: str
    email: str
    session: str


class MailStore:
    """User-JWT requests plus short-lived backend-signed mail commands.

    No service-role key; neither the signing key nor signed commands reach the UI.
    Authorization is rechecked in the database on every command.
    """

    def __init__(self, settings, token, client):
        self.settings, self.token, self.client = settings, token, client

    def request(self, method, path, payload=None):
        try:
            response = self.client.request(
                method,
                self.settings.supabase_url + path,
                headers={"apikey": self.settings.anon_key, "Authorization": "Bearer " + self.token},
                json=payload,
            )
            if response.is_error:
                raise Blocked(status=401 if response.status_code == 401 else 403)
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise Blocked(
                "Supabase unavailable; no automatic retry. Refresh durable status before sending again",
                503,
            ) from exc

    def identity(self):
        user = self.request("GET", "/auth/v1/user")
        if not user.get("email_confirmed_at"):
            raise Blocked("A verified application email is required", 401)
        try:
            # Only use claims AFTER Auth has verified this exact token. Never use user_metadata.
            claims = json.loads(base64.urlsafe_b64decode(self.token.split(".")[1] + "==="))
            if str(UUID(claims["sub"])) != str(UUID(user["id"])):
                raise ValueError("Subject mismatch")
            return Principal(
                str(UUID(user["id"])), email_key(user["email"]), str(UUID(claims["session_id"]))
            )
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise Blocked("Fresh Supabase sign-in required", 401) from exc

    def access(self):
        return self.request("POST", "/rest/v1/rpc/outreach_access", {})

    def redeem(self, invitation):
        return self.request(
            "POST",
            "/rest/v1/rpc/redeem_invitation",
            {"secret_hash": hashlib.sha256(invitation.encode()).hexdigest()},
        )

    def command(self, principal, operation, batch_id=None, **payload):
        command = json.dumps(
            {
                "owner": principal.id,
                "session": principal.session,
                "operation": operation,
                "batch_id": batch_id,
                "payload": payload,
                "expires": int(time.time()) + 60,
                "nonce": str(uuid4()),
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
        signature = hmac.new(
            self.settings.signing_secret.encode(), command.encode(), hashlib.sha256
        ).hexdigest()
        return self.request(
            "POST",
            "/rest/v1/rpc/outreach_mail_action",
            {"command": command, "signature": signature},
        )
