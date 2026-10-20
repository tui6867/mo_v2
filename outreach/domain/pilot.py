from dataclasses import dataclass
from email import policy

from .batches import Batch, Message
from .recipients import email_key


@dataclass(frozen=True)
class PilotBatch(Batch):
    transport_policy: str = "user_gmail_v1"

    def manifest(self):
        return dict(super().manifest(), transport_policy=self.transport_policy)


def pilot_batch(sender, recipient, subject, body, capture=False):
    sender, recipient = email_key(sender), email_key(recipient)
    if (
        not subject.strip()
        or len(subject) > 200
        or any(ord(c) < 32 or ord(c) == 127 for c in subject)
    ):
        raise ValueError("Subject must contain 1–200 characters without line breaks")
    if not body.strip() or len(body) > 10000 or "\x00" in body:
        raise ValueError("Plain-text body must contain 1–10,000 characters without NUL")
    batch = PilotBatch(
        (Message(recipient, subject, body, recipient),),
        sender,
        sender,
        test_mode=capture,
        transport_policy="user_capture_v1" if capture else "user_gmail_v1",
    )
    if len(batch.wire_message(0).as_bytes(policy=policy.SMTPUTF8)) > 20000:
        raise ValueError("Encoded message is too large for the pilot")
    return batch
