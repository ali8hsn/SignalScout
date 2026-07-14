"""Digest models — the weekly 'people you should know' email (spec §12)."""

import uuid
from dataclasses import dataclass, field


@dataclass
class DigestEntry:
    person_id: str
    name: str
    score: float
    thesis: str
    school_line: str  # "MIT '26 • AI Research"
    location_line: str  # "From Raleigh, NC — now in SF"
    top_signals: list[str]  # top-3 signal tags
    connection_context: str  # "Followed by 4 known founders on GitHub"
    warm_intro: str  # "Reach out via <seed founder>, who follows them on GitHub"
    why_now: str
    evidence_links: list[dict]  # [{label, url}]
    contact_links: dict  # {github, linkedin, x, email, site}


@dataclass
class Digest:
    generated_at: str
    entries: list[DigestEntry]
    subject: str
    html: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
