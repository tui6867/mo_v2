import os
import smtplib
import ssl
from email import policy
from email.utils import make_msgid

from outreach.domain.batches import Batch
from outreach.domain.outcomes import Outcome, State


class FakeAdapter:
    """No networking; never sends an email, including in authenticated test mode."""

    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [])
        self.calls = []

    def submit(self, batch: Batch, index: int) -> Outcome:
        self.calls.append((batch, index))
        return (
            self.outcomes.pop(0)
            if self.outcomes
            else Outcome(State.ACCEPTED, "Fake submission only", "fake-" + str(index))
        )


class SMTPAdapter:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        keys = (
            "SMTP_HOST",
            "SMTP_PORT",
            "SMTP_USERNAME",
            "SMTP_PASSWORD",
            "SMTP_TLS_MODE",
            "SMTP_TIMEOUT_SECONDS",
        )
        if any(not env.get(k) for k in keys):
            raise ValueError("SMTP configuration incomplete; real sends are disabled")
        self.host, self.username, self.password = (
            env[k] for k in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD")
        )
        self.port, self.timeout = int(env["SMTP_PORT"]), float(env["SMTP_TIMEOUT_SECONDS"])
        self.mode = env["SMTP_TLS_MODE"]
        if (
            self.mode not in ("starttls", "ssl")
            or not 0 < self.timeout <= 120
            or not 0 < self.port < 65536
        ):
            raise ValueError("SMTP needs TLS and a timeout between 0 and 120 seconds")

    def submit(self, batch: Batch, index: int) -> Outcome:
        msg = batch.wire_message(index)
        msgid = make_msgid(domain=batch.sender.split("@", 1)[1])
        msg["Message-ID"] = msgid
        client = None
        submitting = False
        provider_response = None
        try:
            context = ssl.create_default_context()
            if self.mode == "ssl":
                client = smtplib.SMTP_SSL(
                    self.host, self.port, timeout=self.timeout, context=context
                )
            else:
                client = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                client.ehlo()
                client.starttls(context=context)
                client.ehlo()
            client.login(self.username, self.password)
            original_data = client.data

            def record_data(message):
                nonlocal provider_response
                code, response = original_data(message)
                provider_response = f"{code} {response.decode('utf-8', errors='replace')}"[:500]
                return code, response

            # sendmail discards the successful DATA response, which can include
            # a provider queue ID. Preserve it on this connection, not globally.
            client.data = record_data
            addresses = [batch.sender, batch.reply_to, batch.messages[index].to, *batch.bcc]
            unicode_envelope = any(not address.isascii() for address in addresses)
            if unicode_envelope and not client.has_extn("smtputf8"):
                return Outcome(
                    State.FAILED, "Unicode address requires provider SMTPUTF8 support", msgid
                )
            submitting = True
            wire = msg.as_bytes(policy=policy.SMTPUTF8 if unicode_envelope else policy.SMTP)
            refused = client.sendmail(
                batch.sender,
                [batch.messages[index].to, *batch.bcc],
                wire,
                mail_options=("SMTPUTF8", "BODY=8BITMIME") if unicode_envelope else (),
            )
            # Some envelope recipients may be refused while others were accepted.
            detail = "SMTP accepted submission (not delivery)"
            if refused:
                if batch.messages[index].to in refused:
                    detail += "; primary recipient refused, BCC accepted"
                else:
                    detail += "; primary recipient accepted, BCC refused"
            return Outcome(State.ACCEPTED, detail, msgid, provider_response)
        except (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError,
            smtplib.SMTPAuthenticationError,
            smtplib.SMTPNotSupportedError,
        ):
            return Outcome(
                State.FAILED, "SMTP definitely rejected submission", msgid, provider_response
            )
        except (OSError, smtplib.SMTPException):
            return Outcome(
                State.UNKNOWN if submitting else State.FAILED,
                "Submission outcome unknown; do not retry"
                if submitting
                else "Connection/authentication failed before submission",
                msgid,
            )
        finally:
            if client:
                try:
                    client.close()  # QUIT failure must not overwrite an accepted DATA response.
                except OSError:
                    pass
