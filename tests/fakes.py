"""Synthetic executable model, NOT evidence of real PostgreSQL integration."""

import threading
from types import SimpleNamespace


class MemoryStore:
    def __init__(self, limit=300, global_limit=1000):
        self.limit, self.global_limit = limit, global_limit
        self.lock = threading.Lock()
        self.batches = {}
        self.accepted = 0
        self.held = 0
        self.suppressed = set()
        self.authorized = True
        self.fail_finish = False

    def access(self):
        if not self.authorized:
            raise ValueError("Access revoked")
        return {"remaining": self.limit - self.accepted - self.held}

    def suppression(self):
        self.access()
        return self.suppressed

    def action(self, operation, batch_id=None, **data):
        self.access()
        with self.lock:
            if operation == "start":
                if batch_id in self.batches or any(
                    b["hash"] == data["content_hash"] for b in self.batches.values()
                ):
                    raise ValueError("Already started")
                manifest = data["manifest"]
                n = len(manifest["messages"])
                if n > data["batch_limit"]:
                    raise ValueError("Batch limit")
                reserve = 0 if manifest["test_mode"] else n
                if self.held + self.accepted + reserve > min(
                    self.limit, self.global_limit, data["global_hourly"], data["global_daily"]
                ):
                    raise ValueError("Quota exhausted")
                self.held += reserve
                self.batches[batch_id] = {
                    "hash": data["content_hash"],
                    "test": manifest["test_mode"],
                    "cancelled": False,
                    "rows": [
                        dict(ordinal=i, state="not_attempted", claim_token=None) for i in range(n)
                    ],
                }
                return {"id": batch_id}
            batch = self.batches[batch_id]
            rows = batch["rows"]
            if operation == "claim":
                if batch["cancelled"] or batch["hash"] != data["content_hash"]:
                    raise ValueError("Stopped or changed")
                if any(r["state"] == "submitting" for r in rows):
                    raise ValueError("In flight")
                row = next((r for r in rows if r["state"] == "not_attempted"), None)
                if row is None:
                    return None
                if row["ordinal"] != data["expected_ordinal"]:
                    return None
                row.update(state="submitting", claim_token="synthetic-claim")
                return row.copy()
            if operation == "finish":
                if self.fail_finish:
                    raise ValueError("Database unavailable after SMTP")
                row = rows[data["ordinal"]]
                if row["state"] != "submitting" or row["claim_token"] != data["claim_token"]:
                    raise ValueError("Invalid claim")
                row.update(
                    state=data["state"],
                    detail=data["detail"],
                    provider_id=data["provider_id"],
                    provider_response=data["provider_response"],
                )
                if not batch["test"] and data["state"] != "unknown":
                    self.held -= 1
                    self.accepted += data["state"] == "accepted"
                return True
            if operation == "recover":
                for row in rows:
                    if row["state"] == "submitting":
                        row["state"] = "unknown"
                return True
            if operation == "cancel":
                if not batch["cancelled"]:
                    if not batch["test"]:
                        self.held -= sum(r["state"] == "not_attempted" for r in rows)
                    batch["cancelled"] = True
                return True
            if operation == "log":
                return rows
            raise AssertionError(operation)


CONFIG = SimpleNamespace(batch_limit=300, global_hourly=1000, global_daily=1000)
