import secrets
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from .store import Blocked


@dataclass(repr=False)
class Connection:
    id: str
    owner: str
    session: str
    email: str
    password: str
    created: float
    touched: float
    lock: threading.Lock = field(default_factory=threading.Lock)


class Vault:
    """Process memory only, one connection per application session. One API worker.

    Dropping references is best effort, not guaranteed zeroization of Python strings.
    """

    def __init__(self, clock=time.time):
        self.clock, self.items, self.attempts = clock, {}, {}
        self.lock = threading.RLock()

    def prune(self):
        with self.lock:
            now = self.clock()
            for key, item in list(self.items.items()):
                if now - item.touched >= 1800 or now - item.created >= 7200:
                    item.password = ""
                    del self.items[key]
            self.attempts = {
                k: [t for t in times if now - t < 900]
                for k, times in self.attempts.items()
                if any(now - t < 900 for t in times)
            }

    def throttle(self, principal):
        with self.lock:
            self.prune()
            times = self.attempts.setdefault((principal.id, principal.session), [])
            if len(times) >= 5 or len(self.attempts) > 1000:
                raise Blocked("Too many connection attempts; wait 15 minutes", 429)
            times.append(self.clock())

    def add(self, principal, password):
        with self.lock:
            self.prune()
            self.disconnect_session(principal)
            if len(self.items) >= 100:
                raise Blocked("Connection capacity reached", 503)
            item = Connection(
                secrets.token_urlsafe(32),
                principal.id,
                principal.session,
                principal.email,
                password,
                self.clock(),
                self.clock(),
            )
            self.items[item.id] = item
            return self.public(item)

    def get(self, principal, connection_id):
        with self.lock:
            self.prune()
            item = self.items.get(connection_id)
            if not item or (item.owner, item.session, item.email) != (
                principal.id,
                principal.session,
                principal.email,
            ):
                raise Blocked("Connection missing or expired; reconnect and preview again", 409)
            return item

    def public(self, item):
        return {
            "id": item.id,
            "email": item.email,
            "expires_at": min(item.created + 7200, item.touched + 1800),
        }

    def status(self, principal):
        with self.lock:
            self.prune()
            return next(
                (
                    self.public(c)
                    for c in self.items.values()
                    if (c.owner, c.session, c.email)
                    == (principal.id, principal.session, principal.email)
                ),
                None,
            )

    @contextmanager
    def use(self, principal, connection_id):
        item = self.get(principal, connection_id)
        if not item.lock.acquire(blocking=False):
            raise Blocked("A send is already in progress", 409)
        try:
            # Disconnect/expiry while waiting must not resurrect a connection.
            self.get(principal, connection_id)
            item.touched = self.clock()
            yield item
        finally:
            item.lock.release()

    def disconnect_session(self, principal):
        with self.lock:
            for key, item in list(self.items.items()):
                if (item.owner, item.session) == (principal.id, principal.session):
                    item.password = ""
                    del self.items[key]

    def clear(self):
        with self.lock:
            for item in self.items.values():
                item.password = ""
            self.items.clear()
