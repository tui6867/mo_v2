from string import Formatter
from urllib.parse import urlsplit

KNOWN = {"first", "last", "company", "job_title", "job_url", "my_name"}


def validate_job(values: dict[str, str]) -> None:
    for field in ("company", "job_title", "job_url", "my_name"):
        if not values.get(field, "").strip():
            raise ValueError(f"Required job field: {field}")
    url = urlsplit(values["job_url"])
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise ValueError("Job URL must be an http(s) URL without credentials")


def render(template: str, values: dict[str, str]) -> str:
    if not template.strip():
        raise ValueError("Subject and body are required")
    try:
        for _, field, spec, conversion in Formatter().parse(template):
            if field is not None:
                if field not in KNOWN or spec or conversion:
                    raise ValueError(f"Unsupported placeholder: {field}")
                if not values.get(field, "").strip():
                    raise ValueError(f"Missing value for placeholder: {field}")
        return template.format_map(values)
    except (KeyError, IndexError) as exc:
        raise ValueError("Invalid template") from exc
