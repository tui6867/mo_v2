import csv
import io
import re
import unicodedata
from dataclasses import dataclass, replace
from email.utils import parseaddr

from email_validator import EmailNotValidError, validate_email

PATTERNS = ("first.last", "flast", "firstl", "first")


def normalize_email(value: str) -> str:
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc


def email_key(value: str) -> str:
    # Deliberately conservative deduplication for case-sensitive local parts.
    # Match the database's lower(email) comparison; casefold would transform
    # Unicode local parts such as ß to a different address (ss).
    return normalize_email(value).lower()


def split_name(value: str) -> tuple[str, str]:
    parts = value.strip().split(maxsplit=1)
    return (parts[0], parts[1] if len(parts) > 1 else "") if parts else ("", "")


def generate(first: str, last: str, pattern: str, domain: str) -> str:
    if pattern not in PATTERNS:
        raise ValueError("Only first.last, flast, firstl and first are supported")
    # Do not invent a transliteration or silently remove name punctuation/whitespace.
    first_part, last_part = (unicodedata.normalize("NFC", n).lower() for n in (first, last))
    if not first_part or (pattern != "first" and not last_part):
        raise ValueError("This pattern requires first and last names")
    if any(not c.isalpha() for c in first_part + last_part):
        raise ValueError(
            "Compound/punctuated names need an explicit address; no automatic stripping"
        )
    local = {
        "first.last": first_part + "." + last_part,
        "flast": first_part[:1] + last_part,
        "firstl": first_part + last_part[:1],
        "first": first_part,
    }[pattern]
    return normalize_email(local + "@" + domain.strip())


@dataclass(frozen=True)
class Recipient:
    first_name: str = ""
    last_name: str = ""
    explicit_email: str = ""
    generated_email: str = ""
    chosen_email: str = ""
    source: str = "manual"
    source_row: int = 0
    validation: str = ""


def resolve(record: Recipient, pattern: str, domain: str) -> Recipient:
    if record.explicit_email:
        try:
            email = normalize_email(record.explicit_email)
            return replace(record, chosen_email=email, validation="Explicit email; syntax valid")
        except ValueError as exc:
            return replace(record, chosen_email="", validation=f"Invalid explicit email: {exc}")
    try:
        email = generate(record.first_name, record.last_name, pattern, domain)
        return replace(
            record,
            generated_email=email,
            chosen_email=email,
            validation="Generated guess — mailbox NOT verified",
        )
    except ValueError as exc:
        return replace(record, chosen_email="", validation=str(exc))


def parse_manual(text: str) -> list[Recipient]:
    records = []
    for row, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        if "@" in line or "<" in line or ">" in line:
            structured = re.fullmatch(r"\s*([^<>]*)<([^<>]+)>\s*", line)
            if structured:
                name, _ = parseaddr(line.strip())
                address = structured.group(2).strip()
            else:
                # Validate the entire email-only line; never silently discard a
                # second address or trailing text via permissive parseaddr.
                name, address = "", line.strip()
            first, last = split_name(name)
            records.append(
                Recipient(first, last, explicit_email=address or line.strip(), source_row=row)
            )
        else:
            first, last = split_name(line)
            records.append(Recipient(first, last, source_row=row))
    return records


def csv_preview(data: bytes, max_bytes: int) -> tuple[list[str], list[dict]]:
    if len(data) > max_bytes:
        raise ValueError("CSV exceeds upload limit")
    try:
        reader = csv.DictReader(io.StringIO(data.decode("utf-8-sig")), strict=True)
        headers = reader.fieldnames or []
        if not headers or len(set(headers)) != len(headers) or any(not h.strip() for h in headers):
            raise ValueError("CSV needs unique nonblank headers")
        rows = list(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("Upload a valid UTF-8 CSV with headers") from exc
    if any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ValueError("Malformed CSV row: column count does not match header")
    return headers, rows


def import_csv(data: bytes, mapping: dict[str, str], max_bytes: int) -> list[Recipient]:
    headers, rows = csv_preview(data, max_bytes)
    if not any(mapping.values()) or any(v not in headers for v in mapping.values() if v):
        raise ValueError("Choose valid CSV header mappings")
    records = []
    for row_number, row in enumerate(rows, 2):

        def get(field, row=row):
            return row.get(mapping.get(field, ""), "").strip()

        first, last = get("first_name"), get("last_name")
        if not first and not last:
            first, last = split_name(get("full_name"))
        email = get("email")
        if first or last or email:
            records.append(
                Recipient(first, last, explicit_email=email, source="csv", source_row=row_number)
            )
    return records


def combine(existing: list[Recipient], incoming: list[Recipient], mode: str) -> list[Recipient]:
    if mode not in ("append", "replace"):
        raise ValueError("Choose append or replace")
    return existing + incoming if mode == "append" else list(incoming)


def finalize(records: list[Recipient]) -> list[Recipient]:
    result, seen = [], set()
    for record in records:
        address = normalize_email(record.chosen_email)
        key = email_key(address)
        if key not in seen:
            result.append(replace(record, chosen_email=address))
            seen.add(key)
    if not result:
        raise ValueError("Select at least one valid recipient")
    return result
