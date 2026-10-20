import smtplib
from unittest.mock import Mock

import pytest

from outreach.domain.outcomes import State
from outreach.services.smtp import SMTPAdapter
from tests.test_batches import batch

SMTP_ENV = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": "587",
    "SMTP_USERNAME": "synthetic",
    "SMTP_PASSWORD": "synthetic-not-real",
    "SMTP_TLS_MODE": "starttls",
    "SMTP_TIMEOUT_SECONDS": "10",
}


def test_smtp_acceptance_envelope_bcc_identifiers_tls_no_real_network(monkeypatch):
    client = Mock()
    client.sendmail.return_value = {}
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=client))
    result = SMTPAdapter(SMTP_ENV).submit(batch(bcc="copy@example.com"), 0)
    assert result.state == State.ACCEPTED
    assert result.provider_id.startswith("<")
    assert "not delivery" in result.detail
    args = client.sendmail.call_args.args
    assert args[1] == ["person@example.com", "copy@example.com"]
    assert b"Bcc:" not in args[2] and b"Reply-To: user@example.com" in args[2]
    client.starttls.assert_called_once()
    client.login.assert_called_once_with("synthetic", "synthetic-not-real")


@pytest.mark.parametrize(
    "failure,expected",
    [
        (smtplib.SMTPRecipientsRefused({"synthetic@example.com": (550, b"no")}), State.FAILED),
        (smtplib.SMTPDataError(550, b"no"), State.FAILED),
        (TimeoutError(), State.UNKNOWN),
        (smtplib.SMTPServerDisconnected(), State.UNKNOWN),
    ],
)
def test_smtp_failure_and_ambiguous_data_response(monkeypatch, failure, expected):
    client = Mock()
    client.sendmail.side_effect = failure
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=client))
    result = SMTPAdapter(SMTP_ENV).submit(batch(), 0)
    assert result.state == expected
    assert result.provider_id


def test_provider_data_queue_response_is_preserved(monkeypatch):
    client = Mock()
    client.data.return_value = (250, b"2.0.0 queued as synthetic-queue-42")

    def sendmail(*args, **kwargs):
        client.data(args[2])
        return {}

    client.sendmail.side_effect = sendmail
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=client))
    outcome = SMTPAdapter(SMTP_ENV).submit(batch(), 0)
    assert outcome.state == State.ACCEPTED
    assert outcome.provider_response == "250 2.0.0 queued as synthetic-queue-42"
    assert outcome.provider_id.startswith("<")


def test_pre_submission_failure_is_definite_and_config_fail_closed(monkeypatch):
    monkeypatch.setattr(smtplib, "SMTP", Mock(side_effect=TimeoutError()))
    assert SMTPAdapter(SMTP_ENV).submit(batch(), 0).state == State.FAILED
    with pytest.raises(ValueError):
        SMTPAdapter({})
    with pytest.raises(ValueError):
        SMTPAdapter(dict(SMTP_ENV, SMTP_TLS_MODE="plain"))


def test_partial_refusal_is_accepted_and_close_failure_does_not_hide_acceptance(monkeypatch):
    client = Mock()
    client.sendmail.return_value = {"copy@example.com": (550, b"rejected")}
    client.close.side_effect = OSError()
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=client))
    result = SMTPAdapter(SMTP_ENV).submit(batch(bcc="copy@example.com"), 0)
    assert (
        result.state == State.ACCEPTED
        and "primary recipient accepted, BCC refused" in result.detail
    )


def test_unicode_requires_smtputf8_without_transliteration(monkeypatch):
    from outreach.domain.recipients import Recipient

    client = Mock()
    client.has_extn.return_value = False
    monkeypatch.setattr(smtplib, "SMTP", Mock(return_value=client))
    b = batch(records=[Recipient(first_name="李", chosen_email="李@example.com")])
    assert SMTPAdapter(SMTP_ENV).submit(b, 0).state == State.FAILED
    client.sendmail.assert_not_called()
    client.has_extn.return_value = True
    client.sendmail.return_value = {}
    assert SMTPAdapter(SMTP_ENV).submit(b, 0).state == State.ACCEPTED
    assert client.sendmail.call_args.kwargs["mail_options"] == ("SMTPUTF8", "BODY=8BITMIME")
