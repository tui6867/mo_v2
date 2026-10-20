"""Offline launch configuration check: no API calls, emails or migrations."""

import argparse
import tomllib
from pathlib import Path

from outreach.services.config import Config
from outreach.services.smtp import SMTPAdapter
from outreach.streamlit_settings import load_settings


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--secrets-file", type=Path, help="Local TOML file; values are never printed"
    )
    args = parser.parse_args(argv)
    try:
        secrets = (
            tomllib.loads(args.secrets_file.read_text(encoding="utf-8"))
            if args.secrets_file
            else {}
        )
        settings = load_settings(secrets=secrets)
        config = Config.load(settings)
        if config.real_sends:
            SMTPAdapter(settings)  # Validates configuration only; no connection/submission.
    except (OSError, tomllib.TOMLDecodeError):
        print("BLOCKED: secrets file is missing or invalid TOML; values were not printed")
        return 1
    except ValueError:
        print("BLOCKED: required configuration is missing/invalid; review STREAMLIT_LAUNCH.md")
        return 1
    print("PASS: local configuration validates; live database/auth/SMTP connectivity NOT verified")
    print("Real sends enabled in configuration" if config.real_sends else "Real sends disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
