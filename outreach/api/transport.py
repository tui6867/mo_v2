import smtplib
import ssl
from email import policy
from email.utils import formatdate, make_msgid

from outreach.domain.outcomes import Outcome, State
from outreach.services.smtp import SMTPAdapter

from .store import Blocked


class GmailTransport:
    def verify(self, email, password):
        client = None
        try:
            client = smtplib.SMTP("smtp.gmail.com", 587, timeout=20)
            client.ehlo()
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
            client.login(email, password)
        except (OSError, smtplib.SMTPException) as exc:
            raise Blocked(
                "Gmail connection rejected or unavailable. Check app-password eligibility, credentials and network; no email was submitted",
                422,
            ) from exc
        finally:
            if client:
                client.close()

    def submit(self, connection, batch):
        return SMTPAdapter(
            {
                "SMTP_HOST": "smtp.gmail.com",
                "SMTP_PORT": "587",
                "SMTP_USERNAME": connection.email,
                "SMTP_PASSWORD": connection.password,
                "SMTP_TLS_MODE": "starttls",
                "SMTP_TIMEOUT_SECONDS": "20",
            }
        ).submit(batch, 0)


class CaptureTransport:
    """Distinct plaintext adapter ONLY for the private, egress-isolated test relay.

    Never receives credentials; no configurable host and no external fallback.
    """

    def submit(self, connection, batch):
        if connection.password:
            raise Blocked("Capture must not receive SMTP credentials")
        client, submitting = None, False
        try:
            message = batch.wire_message(0)
            message["Date"] = formatdate(localtime=False, usegmt=True)
            message["Message-ID"] = make_msgid()
            client = smtplib.SMTP("postfix", 587, timeout=20)
            submitting = True
            client.sendmail(
                batch.sender, [batch.messages[0].to], message.as_bytes(policy=policy.SMTP)
            )
            return Outcome(
                State.ACCEPTED,
                "Private Postfix accepted into its queue; inspect Mailpit capture. No external delivery",
                message["Message-ID"],
            )
        except (smtplib.SMTPRecipientsRefused, smtplib.SMTPSenderRefused, smtplib.SMTPDataError):
            return Outcome(State.FAILED, "Capture relay rejected submission")
        except (OSError, smtplib.SMTPException):
            return Outcome(
                State.UNKNOWN if submitting else State.FAILED,
                "Capture outcome unknown; never automatically retry"
                if submitting
                else "Capture relay unavailable",
            )
        finally:
            if client:
                client.close()
