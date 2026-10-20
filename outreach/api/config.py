import base64
import json
import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from outreach.domain.recipients import email_key


def is_public_key(key):
    if key.startswith("sb_publishable_"):
        return True
    try:
        # Classify legacy configuration only; this is NOT JWT authentication.
        claims = json.loads(base64.urlsafe_b64decode(key.split(".")[1] + "==="))
        return claims.get("role") == "anon"
    except (ValueError, IndexError, TypeError, AttributeError):
        return False


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    anon_key: str = field(repr=False)
    origin: str
    signing_secret: str = field(repr=False)
    recipient: str
    transport: str = "capture"
    real_sends: bool = False
    hourly_limit: int = 5
    daily_limit: int = 10

    @classmethod
    def load(cls, env=None):
        env = os.environ if env is None else env
        url = env.get("MAIL_SUPABASE_URL", "").rstrip("/")
        # Deliberately cannot fall back to the copied application's .env/project.
        if url != "https://gnmimpoeqxeczjhvzrrx.supabase.co":
            raise ValueError("MAIL_SUPABASE_URL must identify the approved development project")
        origin = env.get("MAIL_ORIGIN", "https://localhost:8443").rstrip("/")
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.path
            or parsed.query
            or parsed.fragment
            or parsed.username
        ):
            raise ValueError("MAIL_ORIGIN must be an HTTPS origin without a path")
        key, secret = (
            env.get("MAIL_SUPABASE_PUBLISHABLE_KEY", ""),
            env.get("MAIL_SIGNING_SECRET", ""),
        )
        if not is_public_key(key) or len(secret) < 64:
            raise ValueError(
                "Publishable key and a private signing secret (64+ characters) required"
            )
        mode = env.get("MAIL_TRANSPORT", "capture")
        enabled = env.get("MAIL_ENABLE_REAL_SENDS", "false").lower()
        if mode not in ("capture", "gmail") or enabled not in ("true", "false"):
            raise ValueError("Invalid transport or real-send flag")
        hourly, daily = (
            int(env.get("MAIL_HOURLY_LIMIT", "5")),
            int(env.get("MAIL_DAILY_LIMIT", "10")),
        )
        if not 1 <= hourly <= 5 or not 1 <= daily <= 10:
            raise ValueError("Controlled pilot permits at most 5/hour and 10/day globally")
        return cls(
            url,
            key,
            origin,
            secret,
            email_key(env.get("MAIL_TEST_RECIPIENT", "")),
            mode,
            enabled == "true",
            hourly,
            daily,
        )
