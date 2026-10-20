from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

import pytest

from outreach.domain.batches import (
    Attachment,
    approved,
    attachment,
    check_suppression,
    prepare,
    restore,
)
from outreach.domain.recipients import Recipient
from outreach.domain.templates import render
from outreach.services.exports import safe_cell, send_log

VALUES = {
    "company": "Synthetic Co",
    "job_title": "Engineer",
    "job_url": "https://example.com/job",
    "my_name": "Test User",
}


def batch(**kwargs):
    settings = dict(
        records=[
            Recipient(first_name="Synthetic", last_name="Person", chosen_email="person@example.com")
        ],
        values=VALUES,
        subject="{company}: {first}",
        body="Hello {first}\n{job_url}",
        sender="sender@example.com",
        reply_to="user@example.com",
        bcc="",
        attached=None,
        test_mode=False,
        batch_limit=300,
        message_limit=100_000,
    )
    settings.update(kwargs)
    return prepare(**settings)


def test_exact_rendering_and_hash_invalidation():
    b = batch()
    assert b.messages[0].subject == "Synthetic Co: Synthetic"
    assert b.messages[0].body == "Hello Synthetic\nhttps://example.com/job"
    assert approved(b, b.digest)
    changes = [
        batch(subject="changed"),
        batch(body="changed"),
        batch(sender="other@example.com"),
        batch(reply_to="other@example.com"),
        batch(bcc="copy@example.com"),
        batch(attached=Attachment("resume.pdf", b"%PDF-fake", "application/pdf")),
        batch(records=[Recipient(first_name="Synthetic", chosen_email="other@example.com")]),
        batch(test_mode=True),
    ]
    assert all(not approved(changed, b.digest) for changed in changes)
    # Test mode still hashes intended recipients, despite actual To being the verified user.
    test = batch(test_mode=True)
    changed = batch(
        test_mode=True,
        records=[Recipient(first_name="Synthetic", chosen_email="other@example.com")],
    )
    assert test.digest != changed.digest
    assert test.messages[0].to == "user@example.com"


@pytest.mark.parametrize(
    "template", ["{unknown}", "{first!r}", "{first:>10}", "{first.name}", "{first[0]}", "{", "{}"]
)
def test_invalid_placeholders(template):
    with pytest.raises(ValueError):
        render(template, dict(VALUES, first="A"))


def test_missing_placeholder_values_and_required_job_fields():
    with pytest.raises(ValueError):
        render("Hi {first}", dict(VALUES, first=""))
    for field in VALUES:
        with pytest.raises(ValueError):
            batch(values=dict(VALUES, **{field: ""}))


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "file:///x", "https:///x", "https://user:secret@example.com/x"]
)
def test_bad_url(url):
    with pytest.raises(ValueError):
        batch(values=dict(VALUES, job_url=url))


def test_bcc_subject_sender_batch_message_size():
    for changes in (
        {"bcc": "bad"},
        {"bcc": "a@example.com,b@example.com"},
        {"sender": "bad"},
        {"subject": "bad\nheader"},
        {"message_limit": 1},
        {"batch_limit": 0},
        {"test_mode": True, "bcc": "copy@example.com"},
    ):
        with pytest.raises(ValueError):
            batch(**changes)
    b = batch(bcc="copy@example.com")
    assert "Bcc" not in b.wire_message(0)
    assert b.wire_message(0)["Reply-To"] == "user@example.com"


def test_attachment_types_filename_size_and_hash():
    a = attachment("resume.pdf", b"%PDF-1.7 synthetic", 100)
    b = batch(attached=a)
    assert not approved(batch(attached=replace(a, content=b"%PDF-changed")), b.digest)
    assert not approved(batch(attached=replace(a, filename="other.pdf")), b.digest)
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", "<document/>")
    assert attachment("resume.docx", output.getvalue(), 10000).filename == "resume.docx"
    for name, data, limit in [
        ("../x.pdf", b"%PDF-x", 100),
        ("x.exe", b"%PDF-x", 100),
        ("x.pdf", b"not pdf", 100),
        ("x.docx", b"not zip", 100),
        ("x.pdf", b"%PDF-x", 1),
        ("x\n.pdf", b"%PDF-x", 100),
    ]:
        with pytest.raises(ValueError):
            attachment(name, data, limit)


def test_suppression_includes_bcc():
    with pytest.raises(ValueError):
        check_suppression(batch(), {"person@example.com"})
    with pytest.raises(ValueError):
        check_suppression(batch(bcc="copy@example.com"), {"copy@example.com"})


def test_recovery_exact_manifest_and_attachment():
    b = batch(attached=attachment("resume.pdf", b"%PDF-synthetic", 100))
    assert restore(b.manifest(), b.attachment).digest == b.digest
    with pytest.raises(ValueError):
        restore(b.manifest())
    with pytest.raises(ValueError):
        restore(b.manifest(), attachment("resume.pdf", b"%PDF-changed", 100))
    no_attachment = batch()
    assert restore(no_attachment.manifest()) == no_attachment


@pytest.mark.parametrize(
    "value", ["=cmd()", "+cmd", "-cmd", "@cmd", "  =cmd", "\ttext", "\rtext", "\ntext"]
)
def test_spreadsheet_safe_cells(value):
    assert safe_cell(value).startswith("'")
    assert "'" + value.replace('"', '""') in send_log([{"detail": value}]).decode("utf-8-sig")


def test_safe_export_quotes_and_unicode():
    text = send_log(
        [{"email": "synthetic@example.com", "detail": '李, "hello"', "state": "accepted"}]
    ).decode("utf-8-sig")
    assert '"李, ""hello"""' in text
    assert "accepted" in text and "delivered" not in text
