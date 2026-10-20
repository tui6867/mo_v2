import uuid
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import httpx
import streamlit as st

import legal
from outreach.connections import get_api
from outreach.domain.batches import attachment, prepare, restore
from outreach.domain.recipients import (
    PATTERNS,
    combine,
    csv_preview,
    email_key,
    import_csv,
    parse_manual,
    resolve,
)
from outreach.services.config import Config
from outreach.services.exports import send_log
from outreach.services.sending import start, step
from outreach.services.smtp import FakeAdapter, SMTPAdapter
from outreach.streamlit_settings import load_settings


def run():
    page = st.navigation(
        [
            st.Page(outreach_page, title="Outreach", default=True),
            st.Page(privacy_page, title="Privacy", url_path="privacy"),
            st.Page(terms_page, title="Terms", url_path="terms"),
        ]
    )
    page.run()


def privacy_page():
    st.markdown(legal.PRIVACY)


def terms_page():
    st.markdown(legal.TERMS)


def outreach_page():
    st.title("Mass Outreach — invite-only")
    try:
        _workspace(Config.load(load_settings()))
    except (ValueError, httpx.HTTPError) as exc:
        st.error(
            str(exc)
            if isinstance(exc, ValueError)
            else "Service unavailable; no further submission will be attempted"
        )
        st.caption(
            "Setup is incomplete or an operation was blocked. Access and sending remain restricted. Operators: see STREAMLIT_LAUNCH.md for Community Cloud secrets and backend checks."
        )


def _workspace(config):
    store = get_api(config, st.session_state.get("auth_token", ""))
    _session(store, config)


def _session(store, config):
    if st.query_params.get("token_hash"):
        token_hash = st.query_params["token_hash"]
        st.query_params.clear()
        result = store.verify(token_hash)
        st.session_state.clear()
        st.session_state.auth_token = result["access_token"]
        st.rerun()
    if not st.session_state.get("auth_token"):
        st.info(
            "Use your invited address. A magic link verifies email control; an invitation is required for access."
        )
        email = st.text_input("Invited email")
        if st.button("Request magic link"):
            store.magic_link(email)
            st.success("Check your email. After verification, paste your invitation secret below.")
        return
    identity = store.identity()
    if st.session_state.get("identity_id") not in (None, identity.id):
        token = st.session_state.auth_token
        st.session_state.clear()
        st.session_state.auth_token = token
    st.session_state.identity_id = identity.id
    st.text("Verified account: " + identity.email)
    if st.button("Sign out / clear session"):
        st.session_state.clear()
        st.rerun()
    try:
        account = store.access()
    except ValueError:
        secret = st.text_input("Invitation secret", type="password")
        if st.button("Redeem invitation"):
            store.redeem(secret)
            st.rerun()
        st.info(
            "A valid, unused invitation for this verified email is required. Revoked access cannot be redeemed again."
        )
        return
    st.text(
        f"Plan: {account['plan']} · Remaining UTC daily allowance: {account['remaining']} of {account['daily_limit']}"
    )
    st.caption(
        "Accepted submissions count, not delivery. Pending/unknown real submissions hold allowance conservatively."
    )
    _admin(store, account)
    with st.expander("Do-not-contact / suppression list"):
        suppressed_email = st.text_input("Address to suppress")
        if st.button("Add suppression"):
            store.action("suppress", email=email_key(suppressed_email))
            st.success("Address suppressed for your account")
        st.text("\n".join(sorted(store.suppression())) or "No suppression entries")
    _recovery(store, config)
    _draft(store, config, identity.email)


def _admin(store, account):
    if not account["is_admin"]:
        return
    with st.expander("Administrator"):
        email = st.text_input("New invited email")
        days = st.number_input("Invitation lifetime (days)", 1, 30, 7)
        if st.button("Issue invitation"):
            token = store.issue(email, (datetime.now(UTC) + timedelta(days=days)).isoformat())
            st.warning(
                "Share this secret privately with the invited person. It is displayed once, not stored in plaintext."
            )
            st.code(token)
        target = st.text_input("Invitation or user UUID to revoke")
        kind = st.selectbox("Revocation type", ("invitation", "user"))
        if st.button("Revoke selected ID"):
            store.action("revoke_" + kind, id=str(uuid.UUID(target)))
            st.success("Revocation saved")


def _recovery(store, config):
    with st.expander("Previous batches / recovery"):
        batches = store.action("list")
        if not batches:
            st.text("No batches yet")
            return
        selected = st.selectbox(
            "Batch", batches, format_func=lambda b: b["id"] + " · " + b["status"]
        )
        rows = store.action("log", selected["id"])
        st.dataframe(rows, hide_index=True)
        st.download_button("Export previous send log", send_log(rows), "send-log.csv", "text/csv")
        st.caption(
            "Wait five minutes after an interruption. Recovery marks stale submitting outcomes unknown; it never resends them. Review the persisted exact batch and reupload any identical attachment to continue pending recipients."
        )
        if st.button("Recover interrupted checkpoints"):
            store.action("recover", selected["id"])
            st.success("Recovered checkpoints; unknown outcomes will not be retried")
        if st.button("Cancel pending recipients in selected batch"):
            store.action("cancel", selected["id"])
            st.success("Cancelled; unused reservations released")
        if selected["status"] == "started":
            persisted = store.action("get", selected["id"])
            manifest = persisted["manifest"]
            st.text("Persisted From: " + manifest["sender"])
            st.text("Persisted Reply-To: " + manifest["reply_to"])
            st.text("Persisted BCC: " + (", ".join(manifest["bcc"]) or "none"))
            for message in manifest["messages"]:
                st.text("To: " + message["to"] + " · Subject: " + message["subject"])
                st.code(message["body"], language=None)
            attached = None
            if manifest["attachment"]:
                st.text("Required attachment metadata: " + str(manifest["attachment"]))
                upload = st.file_uploader(
                    "Reupload identical recovery attachment",
                    type=["pdf", "docx"],
                    key="recovery_attachment_" + selected["id"],
                )
                if upload is None:
                    return
                if upload.size > config.max_attachment:
                    raise ValueError("Recovery attachment exceeds size limit")
                attached = attachment(upload.name, upload.getvalue(), config.max_attachment)
            recovered = restore(manifest, attached)
            if recovered.digest != persisted["content_hash"]:
                raise ValueError("Persisted batch hash mismatch; continuation blocked")
            reviewed = st.checkbox(
                "I reviewed and approve this exact recovered batch",
                key="recovered_review_" + recovered.digest,
            )
            can_continue = (
                reviewed
                and any(r["state"] == "not_attempted" for r in rows)
                and not any(r["state"] == "submitting" for r in rows)
            )
            if not recovered.test_mode and not config.real_sends:
                st.warning("Real recovery sends are disabled in server configuration")
                return
            if st.button(
                "Submit next pending recipient in recovered batch", disabled=not can_continue
            ):
                ordinal = next(r["ordinal"] for r in rows if r["state"] == "not_attempted")
                step(
                    store,
                    recovered,
                    selected["id"],
                    FakeAdapter() if recovered.test_mode else SMTPAdapter(load_settings()),
                    ordinal,
                )
                st.rerun()


def _draft(store, config, email):
    st.subheader("1 · Job and recipients")
    values = {
        key: st.text_input(label)
        for key, label in (
            ("company", "Company"),
            ("job_title", "Job title"),
            ("job_url", "Job URL"),
            ("my_name", "Your name"),
        )
    }
    pattern = st.selectbox("Generated email pattern", PATTERNS)
    domain = st.text_input("Organization domain")
    st.caption(
        "Generated addresses are guesses, never verified mailboxes. Unicode names are preserved. Compound/punctuated names need explicit emails."
    )
    manual = st.text_area("Manual recipients: one name, email, or Name <email> per line")
    records = parse_manual(manual)
    upload = st.file_uploader("Recipient CSV (UTF-8, headers required)", type=["csv"])
    if upload is not None:
        if upload.size > config.max_csv:
            raise ValueError("CSV exceeds configured upload size")
        data = upload.getvalue()
        headers, preview = csv_preview(data, config.max_csv)
        st.dataframe(preview[:10], hide_index=True)
        mapping = {}
        for field in ("first_name", "last_name", "full_name", "email"):
            aliases = {
                "full_name": ("full_name", "full name", "name"),
                "first_name": ("first_name", "first name", "first"),
                "last_name": ("last_name", "last name", "last"),
                "email": ("email", "email address"),
            }[field]
            default = next((h for h in headers if h.lower().strip() in aliases), "")
            mapping[field] = st.selectbox(
                "Map " + field, ["", *headers], index=(["", *headers]).index(default)
            )
        mode = st.radio(
            "How should CSV combine with manual entries?", ("append", "replace"), index=None
        )
        if mode is None:
            st.info("Choose append or replace to continue")
            return
        records = combine(records, import_csv(data, mapping, config.max_csv), mode)
    resolved = [resolve(r, pattern, domain) for r in records]
    if not resolved:
        st.info("Add recipients to continue")
        return
    editor_rows = [{"selected": bool(r.chosen_email), **asdict(r)} for r in resolved]
    # Widget identities change with import/generation input, not message draft changes.
    import hashlib
    import json

    editor_key = hashlib.sha256(json.dumps(editor_rows, sort_keys=True).encode()).hexdigest()
    edited = st.data_editor(
        editor_rows,
        key="recipients_" + editor_key,
        hide_index=True,
        disabled=["explicit_email", "generated_email", "source", "source_row", "validation"],
    )
    selected = [
        replace(
            r,
            first_name=row["first_name"],
            last_name=row["last_name"],
            chosen_email=row["chosen_email"],
        )
        for r, row in zip(resolved, edited, strict=True)
        if row["selected"]
    ]
    st.subheader("2 · Exact message review")
    subject = st.text_input("Subject", "{company} — {job_title}")
    body = st.text_area(
        "Body",
        "Hello {first},\n\nI'm {my_name}, interested in {job_title} at {company}.\n{job_url}\n\nThank you.",
    )
    st.caption(
        "Placeholders: {first}, {last}, {company}, {job_title}, {job_url}, {my_name}. Email-only recipients need a greeting without {first}."
    )
    test_mode = st.toggle("Fake test mode — no email leaves this application", value=True)
    bcc = st.text_input("Optional BCC (one address)", disabled=test_mode)
    resume = st.file_uploader("Resume (PDF or DOCX; not malware-scanned)", type=["pdf", "docx"])
    attached = None
    if resume:
        if resume.size > config.max_attachment:
            raise ValueError("Attachment exceeds configured upload limit")
        attached = attachment(resume.name, resume.getvalue(), config.max_attachment)
    batch = prepare(
        selected,
        values,
        subject,
        body,
        config.sender,
        email,
        "" if test_mode else bcc,
        attached,
        test_mode,
        config.batch_limit,
        config.max_message,
    )
    st.text("Actual From: " + batch.sender)
    st.text("Actual Reply-To: " + batch.reply_to)
    st.text("BCC: " + (", ".join(batch.bcc) or "none"))
    for index, message in enumerate(batch.messages):
        with st.expander(f"Exact message {index + 1} of {len(batch.messages)}"):
            st.text("To: " + message.to)
            if test_mode:
                st.text(
                    "Intended recipient (fake mode does not contact them): " + message.intended_to
                )
            st.text("Subject: " + message.subject)
            st.code(message.body, language=None)
            if attached:
                st.text(f"Attachment: {attached.filename} ({len(attached.content)} bytes)")
    st.caption(
        "SMTP acceptance does not establish delivery. No sending from your personal mailbox."
    )
    if not test_mode and not config.real_sends:
        st.warning("Real sends are disabled in server configuration")
        return
    if st.checkbox(
        "I reviewed every exact message, recipient, sender, Reply-To, BCC and attachment",
        key="review_" + batch.digest,
    ):
        if st.button("Approve exact batch", key="approve_" + batch.digest):
            st.session_state.approval_hash = batch.digest
            st.session_state.draft_id = str(uuid.uuid4())
    if st.session_state.get("approval_hash") != batch.digest:
        st.info("Approval is required and invalidates whenever the exact batch changes")
        return
    active = (
        st.session_state.get("active_id")
        if st.session_state.get("active_hash") == batch.digest
        else None
    )
    if not active:
        if st.button("Start approved batch / reserve allowance"):
            batch_id = st.session_state.draft_id
            start(store, batch, st.session_state.approval_hash, batch_id, config)
            st.session_state.active_id, st.session_state.active_hash = batch_id, batch.digest
            st.rerun()
        return
    rows = store.action("log", active)
    completed = sum(r["state"] not in ("not_attempted", "submitting") for r in rows)
    accepted = sum(r["state"] == "accepted" for r in rows)
    st.progress(
        completed / len(rows),
        text=f"Email {completed} of {len(rows)} — {accepted} accepted submissions (not delivery)",
    )
    st.dataframe(rows, hide_index=True)
    st.download_button(
        "Download spreadsheet-safe send log", send_log(rows), "send-log.csv", "text/csv"
    )
    st.caption(
        "Session-bound: explicitly continue one recipient at a time. Closing the app stops further submissions. Cancelling preserves completed outcomes; unknown outcomes are never retried."
    )
    if st.button("Cancel remaining recipients"):
        store.action("cancel", active)
        st.session_state.pop("active_id", None)
        st.rerun()
    pending = any(r["state"] == "not_attempted" for r in rows)
    submitting = any(r["state"] == "submitting" for r in rows)
    if st.button(
        "Submit next recipient" if not test_mode else "Simulate next recipient",
        disabled=not pending or submitting,
    ):
        adapter = FakeAdapter() if test_mode else SMTPAdapter(load_settings())
        ordinal = next(r["ordinal"] for r in rows if r["state"] == "not_attempted")
        step(store, batch, active, adapter, ordinal)
        st.rerun()
