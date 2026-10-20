from dataclasses import dataclass
from datetime import datetime

from .recipients import email_key


@dataclass(frozen=True)
class Invitation:
    email: str
    expires_at: datetime
    redeemed_at: datetime | None = None
    revoked_at: datetime | None = None

    def validate_redemption(self, verified_email: str, now: datetime):
        if self.revoked_at or self.redeemed_at or self.expires_at <= now:
            raise ValueError("Invitation expired, revoked or already redeemed")
        if email_key(self.email) != email_key(verified_email):
            raise ValueError("Invitation belongs to a different verified address")
