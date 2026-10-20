import csv
import io


def safe_cell(value) -> str:
    value = str(value if value is not None else "")
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def send_log(rows: list[dict]) -> bytes:
    fields = (
        "ordinal",
        "email",
        "state",
        "detail",
        "provider_id",
        "provider_response",
        "updated_at",
        "test_mode",
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        writer.writerow({field: safe_cell(row.get(field, "")) for field in fields})
    return output.getvalue().encode("utf-8-sig")
