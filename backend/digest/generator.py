"""DigestGenerator: top unknown candidates -> evidence-backed, contactable digest.

Hard rule from the plan: nobody enters the digest without a LinkedIn plus at
least one other contact method.
"""

import html as html_lib
from datetime import datetime
from pathlib import Path

from backend.db.repositories.digests import DigestRepository
from backend.domain.digest import Digest, DigestEntry
from backend.services.candidate_service import CandidateService

TEMPLATE_PATH = Path(__file__).parent / "template.html"


class DigestGenerator:
    def __init__(self, candidates: CandidateService, digests: DigestRepository, out_dir: Path, size: int = 8):
        self.candidates = candidates
        self.digests = digests
        self.out_dir = out_dir
        self.size = size

    def generate(self) -> Digest:
        self.candidates.rescore_all()
        pool = self.candidates.list_candidates("discovery")
        eligible = [c for c in pool if self._contactable(c)]
        picks = eligible[: self.size]

        entries = []
        for candidate in picks:
            school_line = " • ".join(
                filter(None, [self._school_line(candidate), candidate.get("area")])
            )
            entries.append(
                DigestEntry(
                    person_id=candidate["id"], name=candidate["name"],
                    score=candidate["score"], thesis=candidate.get("thesis") or "",
                    school_line=school_line,
                    location_line=self._location_line(candidate),
                    top_signals=[s["summary"] or s["type"] for s in candidate["top_signals"]],
                    connection_context=candidate.get("connection_context") or "",
                    warm_intro=candidate.get("warm_intro") or "",
                    why_now=candidate.get("why_now") or "",
                    evidence_links=[
                        {"label": s["type"], "url": ""} for s in candidate["top_signals"]
                    ],
                    contact_links=candidate.get("contact_links") or {},
                )
            )

        now = datetime.now()
        today = now.date().isoformat()
        digest = Digest(
            generated_at=now.isoformat(timespec="seconds"),
            subject=f"Signal Scout — {len(entries)} people you should know ({today})",
            entries=entries,
        )
        digest.html = self._render(digest)
        self.digests.save(digest)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        (self.out_dir / f"digest-{today}.html").write_text(digest.html)
        return digest

    @staticmethod
    def _contactable(candidate: dict) -> bool:
        links = candidate.get("contact_links") or {}
        others = [k for k in ("x", "email", "site", "github") if k in links]
        return "linkedin" in links and len(others) >= 1

    @staticmethod
    def _school_line(candidate: dict) -> str:
        school = candidate.get("school") or ""
        year = candidate.get("graduation_year")
        return f"{school} '{str(year)[2:]}" if school and year else school

    @staticmethod
    def _location_line(candidate: dict) -> str:
        origin = candidate.get("origin_location")
        current = candidate.get("current_location")
        if origin and current and origin != current:
            return f"From {origin} — now in {current}"
        return f"Based in {current or origin}" if (current or origin) else ""

    def _render(self, digest: Digest) -> str:
        template = TEMPLATE_PATH.read_text()
        blocks = []
        for i, entry in enumerate(digest.entries, 1):
            esc = html_lib.escape
            tags = "".join(f'<span class="tag">{esc(t)}</span>' for t in entry.top_signals)
            links = "".join(
                f'<a href="{esc(url)}">{esc(label)} →</a>'
                for label, url in entry.contact_links.items()
            )
            context_bits = []
            if entry.connection_context:
                context_bits.append(f'<p class="context"><strong>Orbit:</strong> {esc(entry.connection_context)}</p>')
            if entry.warm_intro:
                context_bits.append(f'<p class="context"><strong>Intro path:</strong> {esc(entry.warm_intro)}</p>')
            if entry.why_now:
                context_bits.append(f'<p class="whynow">{esc(entry.why_now)}</p>')
            blocks.append(f"""
  <div class="entry">
    <span class="score">{entry.score:.0f}</span>
    <div class="rank">#{i:03d}</div>
    <h2>{esc(entry.name)}</h2>
    <div class="subline">{esc(entry.school_line)}{" &middot; " + esc(entry.location_line) if entry.location_line else ""}</div>
    <p class="thesis">{esc(entry.thesis)}</p>
    <div class="tags">{tags}</div>
    {"".join(context_bits)}
    <div class="links">{links}</div>
  </div>""")
        return (
            template
            .replace("{{COUNT}}", str(len(digest.entries)))
            .replace("{{DATE}}", digest.generated_at[:10])
            .replace("{{ENTRIES}}", "\n".join(blocks))
        )
