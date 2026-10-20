import hashlib
import secrets
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

from outreach.domain.recipients import email_key, normalize_email
from outreach.services.config import Config


@dataclass(frozen=True)
class Identity:
    id: str
    email: str


class Supabase:
    """Server-side HTTP client using the user's JWT, never a service-role key.

    Protected operations use SQL functions that check auth.uid(), current access,
    ownership and admin role in the database on every call.
    """

    def __init__(self, config: Config, token: str = "", client=None):
        self.config, self.token = config, token
        self.client = client or httpx.Client(timeout=20)

    def request(self, method: str, path: str, payload=None):
        headers = {"apikey": self.config.anon_key}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        response = self.client.request(
            method,
            self.config.supabase_url + path,
            headers=headers,
            json=payload,
        )
        if response.is_error:
            # Never surface credentials, auth tokens or raw SMTP/server diagnostics.
            if path.startswith("/rest/"):
                try:
                    message = response.json().get("message", "Protected operation rejected")
                except ValueError:
                    message = "Database unavailable; operation blocked"
                raise ValueError(message)
            raise ValueError("Authentication failed or unavailable; request a fresh magic link")
        return response.json() if response.content else None

    def magic_link(self, email: str):
        # Does not grant application access: redemption still needs a verified JWT.
        self.request(
            "POST",
            "/auth/v1/otp?" + urlencode({"redirect_to": self.config.redirect_url}),
            {
                "email": normalize_email(email),
                "create_user": True,
            },
        )

    def verify(self, token_hash: str):
        return self.request("POST", "/auth/v1/verify", {"token_hash": token_hash, "type": "email"})

    def identity(self) -> Identity:
        data = self.request("GET", "/auth/v1/user")
        if not data.get("email_confirmed_at"):
            raise ValueError("Verify control of your invited email address first")
        return Identity(data["id"], normalize_email(data["email"]))

    def rpc(self, name: str, **params):
        return self.request("POST", "/rest/v1/rpc/" + name, params)

    def access(self):
        return self.rpc("outreach_access")

    def redeem(self, token: str):
        return self.rpc("redeem_invitation", secret_hash=hashlib.sha256(token.encode()).hexdigest())

    def issue(self, email: str, expires_at: str):
        token = secrets.token_urlsafe(32)
        self.rpc(
            "issue_invitation",
            invited_email=email_key(email),
            secret_hash=hashlib.sha256(token.encode()).hexdigest(),
            expires=expires_at,
        )
        return token

    def action(self, action: str, batch_id: str | None = None, **data):
        return self.rpc("outreach_action", operation=action, target_batch=batch_id, payload=data)

    def suppression(self):
        return {email_key(row["email"]) for row in self.action("suppressions")}
