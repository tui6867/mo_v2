import asyncio
import hashlib
import hmac
import time
from contextlib import asynccontextmanager, suppress
from typing import Annotated
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, SecretStr
from starlette.middleware.trustedhost import TrustedHostMiddleware

from outreach.domain.outcomes import Outcome, State
from outreach.domain.pilot import pilot_batch

from .config import Settings
from .store import Blocked, MailStore
from .transport import CaptureTransport, GmailTransport
from .vault import Vault


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Connect(Input):
    app_password: SecretStr = SecretStr("")


class Redeem(Input):
    invitation: SecretStr


class Draft(Input):
    connection_id: str = Field(min_length=20, max_length=100)
    recipient: str = Field(max_length=254)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10000)


class Send(Draft):
    approval: str = Field(min_length=64, max_length=64, pattern=r"^[a-f0-9]{64}$")
    expires_at: int
    confirmed: bool


def create_app(settings=None, client=None, vault=None, transport=None, store_factory=None):
    settings = settings or Settings.load()
    client = client or httpx.Client(timeout=20, follow_redirects=False)
    vault = vault or Vault()
    transport = transport or (
        GmailTransport() if settings.transport == "gmail" else CaptureTransport()
    )
    store_factory = store_factory or (lambda token: MailStore(settings, token, client))

    @asynccontextmanager
    async def lifespan(app):
        async def clean():
            while True:
                await asyncio.sleep(60)
                vault.prune()

        task = asyncio.create_task(clean())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            vault.clear()
            client.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[httpx.URL(settings.origin).host])

    @app.middleware("http")
    async def boundary(request, call_next):
        if request.method not in ("GET", "HEAD") and (
            request.headers.get("origin") != settings.origin or request.url.scheme != "https"
        ):
            return JSONResponse(
                {"detail": "Use the configured HTTPS application origin"}, status_code=403
            )
        if request.method not in ("GET", "HEAD"):
            # Bound the actual streamed body, not just the attacker-controlled Content-Length.
            data = bytearray()
            async for chunk in request.stream():
                data.extend(chunk)
                if len(data) > 65536:
                    return JSONResponse({"detail": "Request too large"}, status_code=413)
            request._body = bytes(data)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Blocked)
    async def blocked(request, exc):
        return JSONResponse(
            {"detail": exc.detail}, status_code=exc.status, headers={"Cache-Control": "no-store"}
        )

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        # FastAPI's default includes submitted inputs; never reflect passwords or tokens.
        return JSONResponse({"detail": "Invalid request fields"}, status_code=422)

    def identity(request: Request):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer ") or len(header) > 16000:
            raise Blocked("Sign in first", 401)
        store = store_factory(header[7:])
        return store, store.identity()

    IdentityPair = Annotated[tuple, Depends(identity)]

    def authorized(pair: IdentityPair):
        store, principal = pair
        store.access()
        store.command(principal, "check")  # Also validates the Auth session still exists.
        return store, principal

    AuthorizedPair = Annotated[tuple, Depends(authorized)]

    def live_gate():
        if settings.transport == "gmail" and not settings.real_sends:
            raise Blocked("Live Gmail is disabled by the operator", 409)

    def render(principal, draft):
        if draft.recipient.lower().strip() != settings.recipient:
            raise Blocked("Only the operator's test-owned recipient is permitted", 422)
        try:
            return pilot_batch(
                principal.email,
                draft.recipient,
                draft.subject,
                draft.body,
                settings.transport == "capture",
            )
        except ValueError as exc:
            raise Blocked(str(exc), 422) from exc

    def approval(principal, draft, batch, expiry):
        value = f"{principal.id}:{principal.session}:{draft.connection_id}:{batch.digest}:{expiry}"
        return hmac.new(
            settings.signing_secret.encode(), value.encode(), hashlib.sha256
        ).hexdigest()

    @app.get("/api/health")
    def health():
        return {
            "status": "ok",
            "transport": settings.transport,
            "live_enabled": settings.real_sends and settings.transport == "gmail",
        }

    @app.get("/api/config")
    def public_config():
        return {
            "supabase_url": settings.supabase_url,
            "publishable_key": settings.anon_key,
            "transport": settings.transport,
            "live_enabled": settings.real_sends and settings.transport == "gmail",
        }

    @app.post("/api/invitation")
    def redeem(data: Redeem, pair: IdentityPair):
        return pair[0].redeem(data.invitation.get_secret_value())

    @app.get("/api/me")
    def me(pair: AuthorizedPair):
        store, principal = pair
        return {
            "email": principal.email,
            "recipient": settings.recipient,
            "access": store.access(),
            "connection": vault.status(principal),
        }

    @app.post("/api/connection")
    def connect(data: Connect, pair: AuthorizedPair):
        store, principal = pair
        live_gate()
        vault.throttle(principal)
        password = data.app_password.get_secret_value().replace(" ", "")
        if settings.transport == "capture":
            if password:
                raise Blocked("Do not enter real credentials in capture mode", 422)
        else:
            if len(password) != 16 or not password.isascii() or not password.isalpha():
                raise Blocked(
                    "Enter a 16-letter Google app password, not your account password", 422
                )
            transport.verify(principal.email, password)
            # Access may have been revoked during the SMTP handshake.
            store.command(principal, "check")
        return vault.add(principal, password)

    @app.delete("/api/connection")
    def disconnect(pair: IdentityPair):
        vault.disconnect_session(pair[1])
        return {
            "status": "disconnected",
            "note": "This does not revoke your Google app password or cancel an in-flight submission",
        }

    @app.post("/api/preview")
    def preview(data: Draft, pair: AuthorizedPair):
        _, principal = pair
        vault.get(principal, data.connection_id)
        batch = render(principal, data)
        expiry = int(time.time()) + 600
        return {
            "sender": batch.sender,
            "reply_to": batch.reply_to,
            "recipient": batch.messages[0].to,
            "subject": data.subject,
            "body": data.body,
            "approval": approval(principal, data, batch, expiry),
            "expires_at": expiry,
        }

    @app.post("/api/send")
    def send(data: Send, pair: AuthorizedPair):
        store, principal = pair
        live_gate()
        batch = render(principal, data)
        if (
            not data.confirmed
            or not time.time() < data.expires_at <= time.time() + 600
            or not hmac.compare_digest(
                data.approval, approval(principal, data, batch, data.expires_at)
            )
        ):
            raise Blocked("Review and explicitly approve this exact preview again", 409)
        batch_id = str(uuid5(NAMESPACE_URL, principal.id + ":" + batch.digest))
        with vault.use(principal, data.connection_id) as connection:
            # Idempotent start returns the same durable intent for duplicate clicks.
            store.command(
                principal,
                "start",
                batch_id,
                manifest=batch.manifest(),
                content_hash=batch.digest,
                global_hourly=settings.hourly_limit,
                global_daily=settings.daily_limit,
            )
            claimed = store.command(
                principal, "claim", batch_id, content_hash=batch.digest, expected_ordinal=0
            )
            if claimed is not None:
                try:
                    outcome = transport.submit(connection, batch)
                    if outcome.state not in (State.ACCEPTED, State.FAILED, State.UNKNOWN):
                        raise ValueError("Invalid adapter outcome")
                except Exception:
                    outcome = Outcome(
                        State.UNKNOWN, "Submission interrupted; never automatically retry"
                    )
                try:
                    store.command(
                        principal,
                        "finish",
                        batch_id,
                        ordinal=0,
                        state=outcome.state.value,
                        detail=outcome.detail,
                        provider_id=outcome.provider_id,
                        provider_response=outcome.provider_response,
                        claim_token=claimed["claim_token"],
                    )
                except Blocked:
                    return JSONResponse(
                        {
                            "id": batch_id,
                            "state": "unknown",
                            "detail": "Database finalization failed. SMTP may have accepted the email. Do not resend; refresh history and recover after five minutes",
                        },
                        status_code=202,
                    )
            return {"id": batch_id, "attempts": store.command(principal, "log", batch_id)}

    @app.get("/api/messages")
    def history(pair: AuthorizedPair):
        return pair[0].command(pair[1], "list")

    @app.get("/api/messages/{batch_id}")
    def status(batch_id: UUID, pair: AuthorizedPair):
        return pair[0].command(pair[1], "log", str(batch_id))

    @app.post("/api/messages/{batch_id}/recover")
    def recover(batch_id: UUID, pair: AuthorizedPair):
        pair[0].command(pair[1], "recover", str(batch_id))
        return pair[0].command(pair[1], "log", str(batch_id))

    return app
