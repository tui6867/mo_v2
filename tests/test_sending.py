from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from types import SimpleNamespace

import pytest

from outreach.domain.batches import Message
from outreach.domain.outcomes import Outcome, State
from outreach.services.sending import start, step
from outreach.services.smtp import FakeAdapter
from tests.fakes import CONFIG, MemoryStore
from tests.test_batches import batch


@pytest.mark.parametrize(
    "state,accepted,held", [(State.ACCEPTED, 1, 0), (State.FAILED, 0, 0), (State.UNKNOWN, 0, 1)]
)
def test_terminal_states_quota_and_identifiers(state, accepted, held):
    store, b = MemoryStore(), batch()
    start(store, b, b.digest, "synthetic-batch", CONFIG)
    adapter = FakeAdapter([Outcome(state, "Synthetic result", "synthetic-provider-id")])
    assert step(store, b, "synthetic-batch", adapter).state == state
    assert store.accepted == accepted and store.held == held
    assert store.action("log", "synthetic-batch")[0]["provider_id"] == "synthetic-provider-id"
    assert step(store, b, "synthetic-batch", adapter) is None
    assert len(adapter.calls) == 1


def test_duplicate_start_and_concurrent_clicks():
    store, b = MemoryStore(), batch()
    b = replace(
        b,
        messages=(
            *b.messages,
            Message("second@example.com", "Synthetic", "body", "second@example.com"),
        ),
    )
    start(store, b, b.digest, "one", CONFIG)
    with pytest.raises(ValueError):
        start(store, b, b.digest, "one", CONFIG)
    with pytest.raises(ValueError):
        start(store, b, b.digest, "different-id", CONFIG)
    adapter = FakeAdapter()

    def click(_):
        try:
            return step(store, b, "one", adapter)
        except ValueError:
            return None

    with ThreadPoolExecutor(2) as pool:
        list(pool.map(click, range(2)))
    assert len(adapter.calls) == 1
    assert store.action("log", "one")[1]["state"] == "not_attempted"


def test_cancel_between_recipients_and_release_unused():
    store, b = MemoryStore(), batch()
    b = replace(
        b,
        messages=(
            *b.messages,
            Message("second@example.com", "Synthetic", "body", "second@example.com"),
        ),
    )
    start(store, b, b.digest, "one", CONFIG)
    adapter = FakeAdapter()
    step(store, b, "one", adapter)
    store.action("cancel", "one")
    store.action("cancel", "one")
    with pytest.raises(ValueError):
        step(store, b, "one", adapter)
    assert store.accepted == 1 and store.held == 0
    assert store.action("log", "one")[1]["state"] == "not_attempted"
    assert len(adapter.calls) == 1


def test_interrupted_batch_database_failure_after_submission():
    store, b = MemoryStore(), batch()
    start(store, b, b.digest, "one", CONFIG)
    store.fail_finish = True
    adapter = FakeAdapter()
    with pytest.raises(ValueError):
        step(store, b, "one", adapter)
    assert store.action("log", "one")[0]["state"] == "submitting"
    with pytest.raises(ValueError):
        step(store, b, "one", adapter)
    store.action("recover", "one")
    assert store.action("log", "one")[0]["state"] == "unknown"
    assert step(store, b, "one", adapter) is None
    assert len(adapter.calls) == 1 and store.held == 1


def test_adapter_exception_is_unknown():
    class Broken:
        def submit(self, *_):
            raise TimeoutError("synthetic timeout")

    store, b = MemoryStore(), batch()
    start(store, b, b.digest, "one", CONFIG)
    assert step(store, b, "one", Broken()).state == State.UNKNOWN


def test_recovery_can_continue_only_unattempted_with_fresh_ordinal():
    store, b = MemoryStore(), batch()
    b = replace(
        b,
        messages=(
            *b.messages,
            Message("second@example.com", "Synthetic", "body", "second@example.com"),
        ),
    )
    start(store, b, b.digest, "one", CONFIG)
    store.action("claim", "one", content_hash=b.digest, expected_ordinal=0)
    store.action("recover", "one")
    adapter = FakeAdapter()
    assert step(store, b, "one", adapter, 0) is None
    assert step(store, b, "one", adapter, 1).state == State.ACCEPTED
    assert len(adapter.calls) == 1
    assert store.action("log", "one")[0]["state"] == "unknown"
    assert store.held == 1 and store.accepted == 1


def test_approval_revocation_and_suppression_block_before_provider():
    store, b = MemoryStore(), batch()
    with pytest.raises(ValueError):
        start(store, b, "old-hash", "one", CONFIG)
    start(store, b, b.digest, "one", CONFIG)
    adapter = FakeAdapter()
    store.suppressed = {"person@example.com"}
    with pytest.raises(ValueError):
        step(store, b, "one", adapter)
    store.suppressed = set()
    store.authorized = False
    with pytest.raises(ValueError):
        step(store, b, "one", adapter)
    assert not adapter.calls


def test_quota_concurrent_reservations_cannot_overspend_reference_model():
    store = MemoryStore(limit=300)
    store.accepted = 299

    def reserve(i):
        b = batch(subject="Synthetic " + str(i))
        try:
            start(store, b, b.digest, str(i), CONFIG)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(8) as pool:
        assert sum(pool.map(reserve, range(20))) == 1
    assert store.held == 1


def test_global_and_user_limits_fake_mode_and_failed_release():
    b = batch()
    store = MemoryStore(global_limit=1)
    start(store, b, b.digest, "one", CONFIG)
    with pytest.raises(ValueError):
        changed = batch(subject="different")
        start(store, changed, changed.digest, "two", CONFIG)
    step(store, b, "one", FakeAdapter([Outcome(State.FAILED)]))
    changed = batch(subject="different")
    start(store, changed, changed.digest, "two", CONFIG)
    test = batch(test_mode=True)
    start(store, test, test.digest, "test", CONFIG)
    step(store, test, "test", FakeAdapter())
    assert store.accepted == 0 and store.held == 1


@pytest.mark.parametrize("hourly,daily", [(1, 1000), (1000, 1)])
def test_separate_application_hourly_and_daily_limit_models(hourly, daily):
    store, b = MemoryStore(), batch()
    config = SimpleNamespace(batch_limit=300, global_hourly=hourly, global_daily=daily)
    start(store, b, b.digest, "first", config)
    step(store, b, "first", FakeAdapter())
    changed = batch(subject="second synthetic batch")
    with pytest.raises(ValueError):
        start(store, changed, changed.digest, "second", config)
