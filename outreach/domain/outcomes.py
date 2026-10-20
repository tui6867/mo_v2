from dataclasses import dataclass
from enum import StrEnum


class State(StrEnum):
    NOT_ATTEMPTED = "not_attempted"
    SUBMITTING = "submitting"
    ACCEPTED = "accepted"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Outcome:
    state: State
    detail: str = ""
    provider_id: str | None = None
    provider_response: str | None = None
