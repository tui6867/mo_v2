from outreach.domain.batches import Batch, approved, check_suppression
from outreach.domain.outcomes import Outcome, State


def start(store, batch: Batch, approval_hash: str, batch_id: str, config):
    if not approved(batch, approval_hash):
        raise ValueError("Content changed; review and approve this exact batch again")
    store.access()
    check_suppression(batch, store.suppression())
    return store.action(
        "start",
        batch_id,
        manifest=batch.manifest(),
        content_hash=batch.digest,
        batch_limit=config.batch_limit,
        global_hourly=config.global_hourly,
        global_daily=config.global_daily,
    )


def step(store, batch: Batch, batch_id: str, adapter, expected_ordinal: int = 0):
    """One session-driven submission, no loop, queue or automatic retry.

    Claim commits before SMTP. If SMTP or finalization is interrupted the durable
    submitting checkpoint becomes unknown on explicit recovery, never retried.
    """
    store.access()
    check_suppression(batch, store.suppression())
    claimed = store.action(
        "claim", batch_id, content_hash=batch.digest, expected_ordinal=expected_ordinal
    )
    if claimed is None:
        return None
    index = claimed["ordinal"]
    try:
        outcome = adapter.submit(batch, index)
        if outcome.state not in (State.ACCEPTED, State.FAILED, State.UNKNOWN):
            outcome = Outcome(State.UNKNOWN, "Adapter returned an invalid terminal state")
    except Exception:
        outcome = Outcome(State.UNKNOWN, "Submission interrupted; never automatically retry")
    # Do not catch a failed DB finalization and proceed to another recipient.
    store.action(
        "finish",
        batch_id,
        ordinal=index,
        state=outcome.state.value,
        detail=outcome.detail,
        provider_id=outcome.provider_id,
        provider_response=outcome.provider_response,
        claim_token=claimed["claim_token"],
    )
    return outcome
