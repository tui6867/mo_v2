import os
from dataclasses import dataclass
from urllib.parse import urlsplit

from outreach.domain.recipients import normalize_email


@dataclass(frozen=True)
class Config:
    supabase_url: str
    anon_key: str
    redirect_url: str
    sender: str
    batch_limit: int
    global_hourly: int
    global_daily: int
    max_attachment: int
    max_message: int
    max_csv: int
    real_sends: bool

    @classmethod
    def load(cls, env=None):
        env = os.environ if env is None else env

        def required(name):
            value = env.get(name, "").strip()
            if not value:
                raise ValueError(f"Missing configuration: {name}")
            return value

        def positive(name):
            try:
                value = int(required(name))
            except ValueError as exc:
                raise ValueError(f"{name} must be a positive integer") from exc
            if value <= 0:
                raise ValueError(f"{name} must be positive")
            return value

        url, redirect = required("SUPABASE_URL"), required("AUTH_REDIRECT_URL")
        if any(urlsplit(u).scheme != "https" or not urlsplit(u).hostname for u in (url, redirect)):
            raise ValueError("Supabase and authentication redirect URLs must use HTTPS")
        if any(
            urlsplit(u).username
            or urlsplit(u).password
            or urlsplit(u).query
            or urlsplit(u).fragment
            for u in (url, redirect)
        ):
            raise ValueError(
                "Supabase and authentication redirect URLs cannot include credentials, query or fragment"
            )
        if required("SENDER_DOMAIN_VERIFIED").lower() != "true":
            raise ValueError("Operator must verify the sender domain before enabling the app")
        return cls(
            url.rstrip("/"),
            required("SUPABASE_ANON_KEY"),
            redirect,
            normalize_email(required("SENDER_EMAIL")),
            positive("BATCH_LIMIT"),
            positive("GLOBAL_HOURLY_LIMIT"),
            positive("GLOBAL_DAILY_LIMIT"),
            positive("MAX_ATTACHMENT_BYTES"),
            positive("MAX_MESSAGE_BYTES"),
            positive("MAX_CSV_BYTES"),
            env.get("ENABLE_REAL_SENDS", "").lower() == "true",
        )
