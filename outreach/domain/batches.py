import hashlib
import json
import zipfile
from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from io import BytesIO
from pathlib import PurePosixPath

from .recipients import Recipient, email_key, finalize, normalize_email
from .templates import render, validate_job


@dataclass(frozen=True)
class Attachment:
    filename: str
    content: bytes
    content_type: str

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


def attachment(filename: str, content: bytes, max_bytes: int) -> Attachment:
    if not content or len(content) > max_bytes:
        raise ValueError("Attachment is empty or exceeds size limit")
    if any(c in filename for c in "\\/\r\n\x00") or PurePosixPath(filename).name != filename:
        raise ValueError("Unsafe attachment filename")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix == ".pdf" and content.startswith(b"%PDF-"):
        return Attachment(filename, content, "application/pdf")
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if (
                    "[Content_Types].xml" in archive.namelist()
                    and "word/document.xml" in archive.namelist()
                ):
                    if sum(i.file_size for i in archive.infolist()) > max_bytes * 20:
                        raise ValueError("DOCX expanded size exceeds limit")
                    return Attachment(
                        filename,
                        content,
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
        except zipfile.BadZipFile:
            pass
    raise ValueError("Only recognizable PDF and DOCX attachments are allowed (not malware-scanned)")


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    body: str
    intended_to: str = ""


@dataclass(frozen=True)
class Batch:
    messages: tuple[Message, ...]
    sender: str
    reply_to: str
    bcc: tuple[str, ...] = ()
    attachment: Attachment | None = None
    test_mode: bool = True

    @property
    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(self.manifest(), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()

    def manifest(self) -> dict:
        return {
            "messages": [vars(m) for m in self.messages],
            "sender": self.sender,
            "reply_to": self.reply_to,
            "bcc": list(self.bcc),
            "test_mode": self.test_mode,
            "attachment": (
                {
                    "filename": self.attachment.filename,
                    "content_type": self.attachment.content_type,
                    "size": len(self.attachment.content),
                    "sha256": self.attachment.digest,
                }
                if self.attachment
                else None
            ),
        }

    def wire_message(self, index: int) -> EmailMessage:
        item = self.messages[index]
        msg = EmailMessage()
        msg["From"], msg["Reply-To"], msg["To"], msg["Subject"] = (
            self.sender,
            self.reply_to,
            item.to,
            item.subject,
        )
        msg.set_content(item.body)
        if self.attachment:
            main, sub = self.attachment.content_type.split("/", 1)
            msg.add_attachment(
                self.attachment.content,
                maintype=main,
                subtype=sub,
                filename=self.attachment.filename,
            )
        # BCC is envelope-only, never an exposed message header.
        return msg


def prepare(
    records: list[Recipient],
    values: dict[str, str],
    subject: str,
    body: str,
    sender: str,
    reply_to: str,
    bcc: str,
    attached: Attachment | None,
    test_mode: bool,
    batch_limit: int,
    message_limit: int,
) -> Batch:
    validate_job(values)
    sender, reply_to = normalize_email(sender), normalize_email(reply_to)
    copies = tuple(dict.fromkeys(normalize_email(a) for a in bcc.split(",") if a.strip()))
    if len(copies) > 1:
        raise ValueError("At most one BCC is supported in this release")
    if test_mode and copies:
        raise ValueError("BCC is disabled in fake test mode")
    selected = finalize(records)
    if len(selected) > batch_limit:
        raise ValueError("Selected recipients exceed batch limit")
    messages = []
    for r in selected:
        fields = dict(values, first=r.first_name, last=r.last_name)
        rendered_subject, rendered_body = render(subject, fields), render(body, fields)
        if "\r" in rendered_subject or "\n" in rendered_subject:
            raise ValueError("Subject cannot contain newlines")
        messages.append(
            Message(
                reply_to if test_mode else r.chosen_email,
                rendered_subject,
                rendered_body,
                r.chosen_email,
            )
        )
    batch = Batch(tuple(messages), sender, reply_to, copies, attached, test_mode)
    if any(
        max(len(batch.wire_message(i).as_bytes(policy=p)) for p in (policy.SMTP, policy.SMTPUTF8))
        + 256
        > message_limit
        for i in range(len(messages))
    ):
        raise ValueError("Total encoded message size exceeds limit")
    return batch


def approved(batch: Batch, approval_hash: str | None) -> bool:
    return approval_hash == batch.digest


def restore(manifest: dict, attached: Attachment | None = None) -> Batch:
    """Recover the persisted exact rendering; attachments must be supplied again."""
    batch = Batch(
        tuple(Message(**message) for message in manifest["messages"]),
        manifest["sender"],
        manifest["reply_to"],
        tuple(manifest["bcc"]),
        attached,
        manifest["test_mode"],
    )
    if batch.manifest() != manifest:
        raise ValueError("Recovery attachment/content differs from the approved batch")
    return batch


def check_suppression(batch: Batch, suppressed: set[str]) -> None:
    targets = [m.to for m in batch.messages] + list(batch.bcc)
    if any(email_key(a) in suppressed for a in targets):
        raise ValueError("Selected recipient or BCC is suppressed; remove it before sending")
