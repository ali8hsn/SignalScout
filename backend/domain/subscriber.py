"""Subscriber and digest-delivery domain models."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Subscriber:
    email: str
    frequency: str
    preferences: dict
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    unsubscribe_token: str = field(default_factory=lambda: str(uuid.uuid4()))
    active: bool = True
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
