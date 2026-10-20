"""Accounts, free trial, phone verification and Stripe subscriptions.

Services (all called over plain HTTPS with `requests`):
  - Supabase (Postgres) stores who has verified a phone and how many trial sends they used.
  - Twilio Verify sends and checks the SMS code.
  - Stripe holds the subscription (weekly, monthly or 3-month plans). We never see card details.

Rules:
  - Every Gmail gets one free trial of TRIAL_SENDS real emails (test-mode sends to yourself are free).
  - The trial needs a verified phone. Each phone number can unlock the trial for one Gmail only.
  - Once a Gmail has a phone attached, it can't be swapped, so one Gmail = one trial.
  - Paying subscribers skip the phone step and the trial limit.
Phone numbers are stored only as a keyed hash, never in plain text.
"""

import hashlib
import hmac
import re

import requests

TRIAL_SENDS = 10
TIMEOUT = 20


class BillingError(Exception):
    """A problem worth showing to the user in plain words. `detail` holds Stripe's own message, for the owner."""

    def __init__(self, msg, detail=""):
        super().__init__(msg)
        self.detail = detail


# ---------------------------------------------------------------- phone helpers
def normalize_phone(raw: str) -> str | None:
    """'(917) 555-0100' -> '+19175550100'. US numbers by default; '+' for other countries."""
    raw = (raw or "").strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        return "+" + digits if 8 <= len(digits) <= 15 else None
    if len(digits) == 10:
        return "+1" + digits
    if len(digits) == 11 and digits.startswith("1"):
        return "+" + digits
    return None


def phone_hash(e164: str, secret: str) -> str:
    return hmac.new(secret.encode(), e164.encode(), hashlib.sha256).hexdigest()


def gmail_trial_key(email: str) -> str:
    """Used instead of a phone when phone verification is off: the trial is tied to the Gmail alone."""
    return "gmail:" + hashlib.sha256(email.strip().lower().encode()).hexdigest()


# ---------------------------------------------------------------- Supabase
class Store:
    """Two tables (see BILLING_SETUP.md for the SQL):
       users(email pk, phone_hash)
       phones(phone_hash pk, trial_email, trial_sends_used)"""

    def __init__(self, url: str, key: str, http=requests):
        self.base = url.rstrip("/") + "/rest/v1"
        self.h = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self.http = http

    def _get(self, table, **eq):
        params = {k: f"eq.{v}" for k, v in eq.items()}
        params["select"] = "*"
        r = self.http.get(f"{self.base}/{table}", headers=self.h, params=params, timeout=TIMEOUT)
        if not r.ok:
            raise BillingError("Couldn't reach the account database. Try again in a minute.")
        rows = r.json()
        return rows[0] if rows else None

    def _upsert(self, table, row):
        h = dict(self.h, Prefer="resolution=merge-duplicates,return=minimal")
        r = self.http.post(f"{self.base}/{table}", headers=h, json=row, timeout=TIMEOUT)
        if not r.ok:
            raise BillingError("Couldn't save to the account database. Try again in a minute.")

    def _insert_if_absent(self, table, row):
        h = dict(self.h, Prefer="resolution=ignore-duplicates,return=minimal")
        r = self.http.post(f"{self.base}/{table}", headers=h, json=row, timeout=TIMEOUT)
        if not r.ok:
            raise BillingError("Couldn't save to the account database. Try again in a minute.")

    def _patch(self, table, match: dict, values: dict):
        params = {k: f"eq.{v}" for k, v in match.items()}
        r = self.http.patch(f"{self.base}/{table}", headers=self.h, params=params, json=values, timeout=TIMEOUT)
        if not r.ok:
            raise BillingError("Couldn't update the account database.")

    # --- public
    def user(self, email):
        return self._get("users", email=email.lower())

    def phone(self, ph):
        return self._get("phones", phone_hash=ph)

    def attach_phone(self, email: str, ph: str) -> bool:
        """Link a verified phone to this Gmail. Returns True if this Gmail got the free trial."""
        email = email.lower()
        u = self.user(email)
        if u and u.get("phone_hash"):
            return self.trial_left(email) > 0  # already attached; nothing changes
        self._insert_if_absent("phones", {"phone_hash": ph, "trial_email": email, "trial_sends_used": 0})
        self._upsert("users", {"email": email, "phone_hash": ph})
        p = self.phone(ph)
        return bool(p and p["trial_email"] == email)

    def trial_left(self, email: str) -> int:
        u = self.user(email.lower())
        if not u or not u.get("phone_hash"):
            return 0
        p = self.phone(u["phone_hash"])
        if not p or p["trial_email"] != email.lower():
            return 0
        return max(0, TRIAL_SENDS - int(p["trial_sends_used"]))

    def use_trial_send(self, email: str):
        u = self.user(email.lower())
        p = self.phone(u["phone_hash"])
        self._patch("phones", {"phone_hash": p["phone_hash"]},
                    {"trial_sends_used": int(p["trial_sends_used"]) + 1})


# ---------------------------------------------------------------- Twilio Verify
class PhoneVerifier:
    def __init__(self, account_sid, auth_token, service_sid, http=requests):
        self.auth = (account_sid, auth_token)
        self.base = f"https://verify.twilio.com/v2/Services/{service_sid}"
        self.http = http

    def send_code(self, e164: str):
        r = self.http.post(f"{self.base}/Verifications", auth=self.auth,
                           data={"To": e164, "Channel": "sms"}, timeout=TIMEOUT)
        if not r.ok:
            try:
                msg = r.json().get("message", "")
            except Exception:
                msg = ""
            raise BillingError(f"Couldn't text that number. {msg}".strip())

    def check_code(self, e164: str, code: str) -> bool:
        r = self.http.post(f"{self.base}/VerificationCheck", auth=self.auth,
                           data={"To": e164, "Code": code.strip()}, timeout=TIMEOUT)
        return r.ok and r.json().get("status") == "approved"


# ---------------------------------------------------------------- Stripe
class Payments:
    def __init__(self, secret_key, app_url, http=requests):
        self.auth = (secret_key, "")
        self.app_url = app_url.rstrip("/")
        self.http = http

    def _req(self, method, path, **kw):
        r = self.http.request(method, f"https://api.stripe.com/v1/{path}", auth=self.auth, timeout=TIMEOUT, **kw)
        if not r.ok:
            try:
                detail = r.json().get("error", {}).get("message", "")
            except Exception:
                detail = ""
            msg = "Couldn't reach the payment system. Try again in a minute."
            raise BillingError(msg, detail)
        return r.json()

    def _customers(self, email):
        return self._req("GET", "customers", params={"email": email.lower(), "limit": 10}).get("data", [])

    def is_subscribed(self, email: str) -> bool:
        for c in self._customers(email):
            subs = self._req("GET", "subscriptions", params={"customer": c["id"], "status": "all", "limit": 10})
            if any(s["status"] in ("active", "trialing", "past_due") for s in subs.get("data", [])):
                return True
        return False

    def checkout_url(self, email: str, price_id: str) -> str:
        existing = self._customers(email)
        data = {
            "mode": "subscription",
            "line_items[0][price]": price_id,
            "line_items[0][quantity]": 1,
            "success_url": self.app_url + "/?paid=1",
            "cancel_url": self.app_url + "/",
            "allow_promotion_codes": "true",
            "payment_method_collection": "always",
        }
        if existing:
            data["customer"] = existing[0]["id"]
        else:
            data["customer_email"] = email.lower()
        return self._req("POST", "checkout/sessions", data=data)["url"]

    def price_info(self, price_id: str) -> dict:
        """Amount and billing period straight from Stripe, e.g. {'amount': 12.0, 'interval': 'week', 'count': 1}."""
        p = self._req("GET", f"prices/{price_id}")
        rec = p.get("recurring") or {}
        return {
            "amount": (p.get("unit_amount") or 0) / 100,
            "currency": (p.get("currency") or "usd").upper(),
            "interval": rec.get("interval", "month"),
            "count": int(rec.get("interval_count") or 1),
            "active": bool(p.get("active", True)),
        }

    def portal_url(self, email: str) -> str | None:
        existing = self._customers(email)
        if not existing:
            return None
        return self._req("POST", "billing_portal/sessions",
                         data={"customer": existing[0]["id"], "return_url": self.app_url + "/"})["url"]


def money(amount: float, currency: str = "USD") -> str:
    sym = "$" if currency.upper() == "USD" else currency.upper() + " "
    return f"{sym}{amount:,.0f}" if float(amount).is_integer() else f"{sym}{amount:,.2f}"


def price_label(info: dict) -> str:
    """{'amount': 75, 'interval': 'month', 'count': 3} -> '$75 every 3 months'."""
    amt = money(info["amount"], info.get("currency", "USD"))
    unit, n = info["interval"], info["count"]
    return f"{amt}/{unit}" if n == 1 else f"{amt} every {n} {unit}s"


def per_month(info: dict) -> float:
    months = {"day": 1 / 30.4, "week": 12 / 52, "month": 1, "year": 12}[info["interval"]] * info["count"]
    return info["amount"] / months
