"""Streamlit secret boundary; domain/services do not depend on Streamlit."""

import os
from collections.abc import Mapping

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

SETTING_NAMES = (
    "SUPABASE_URL",
    "SUPABASE_ANON_KEY",
    "AUTH_REDIRECT_URL",
    "SENDER_EMAIL",
    "SENDER_DOMAIN_VERIFIED",
    "BATCH_LIMIT",
    "GLOBAL_HOURLY_LIMIT",
    "GLOBAL_DAILY_LIMIT",
    "MAX_ATTACHMENT_BYTES",
    "MAX_MESSAGE_BYTES",
    "MAX_CSV_BYTES",
    "ENABLE_REAL_SENDS",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_TLS_MODE",
    "SMTP_TIMEOUT_SECONDS",
)


def load_settings(env: Mapping | None = None, secrets: Mapping | None = None) -> dict[str, str]:
    """Explicit environment overrides TOML, including blank/false values.

    Typed TOML booleans/integers become strings before pure service validation.
    Unknown keys are ignored. No secrets are printed, exported or globally cached.
    """
    env = os.environ if env is None else env
    if secrets is None:
        try:
            secrets = st.secrets.to_dict()
        except (FileNotFoundError, StreamlitSecretNotFoundError):
            secrets = {}
    settings = {}
    for key in SETTING_NAMES:
        value = env[key] if key in env else secrets.get(key)
        if value is not None:
            settings[key] = str(value).lower() if isinstance(value, bool) else str(value)
    return settings
