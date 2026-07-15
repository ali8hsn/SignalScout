"""List, export, approve, update, or reject launch candidates safely."""

import argparse
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.container import Container


def linkedin_search_url(name: str, school: str | None) -> str:
    query = " ".join(filter(None, [name, school]))
    return "https://www.linkedin.com/search/results/people/?keywords=" + urllib.parse.quote(query)


def export_checklist(container: Container, top: int, output: Path) -> None:
    candidates = container.candidate_service.list_candidates("discovery")[:top]
    lines = [
        "# Verification checklist — top unknown discoveries",
        "",
        f"Auto-generated from the live cohort. Review the top {len(candidates)} before any outreach.",
        "Each is a candidate flagged by score; confirm they are a *real, pre-breakout* person.",
        "",
    ]
    for i, c in enumerate(candidates, 1):
        gh = c.get("github_username")
        gh_url = f"https://github.com/{gh}" if gh else "—"
        followers = c.get("github_followers")
        followers_str = f"{followers:,}" if isinstance(followers, int) else "?"
        links = c.get("contact_links") or {}
        email = links.get("email", "").replace("mailto:", "") or "—"
        signal_bits = "; ".join(s.get("summary") or s["type"] for s in c.get("top_signals", [])) or "—"
        if links.get("linkedin"):
            linkedin_line = f"**LinkedIn (resolved):** {links['linkedin']}"
        else:
            linkedin_line = f"**LinkedIn search:** {linkedin_search_url(c['name'], c.get('school'))}"

        lines += [
            f"## {i}. {c['name']}  ·  score {round(c['score'])}",
            "",
            f"- [ ] Confirmed real & pre-breakout",
            f"- **GitHub:** {gh_url}  ({followers_str} followers)",
            f"- **School / area:** {c.get('school') or '—'} · {c.get('area') or '—'}",
            f"- **Location:** {c.get('current_location') or c.get('region') or '—'}",
            f"- **Top signals:** {signal_bits}",
            f"- **Orbit:** {c.get('connection_context') or '—'}",
            f"- **Email:** {email}",
            f"- {linkedin_line}",
            "",
        ]

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines))
    print(f"wrote {output} ({len(candidates)} candidates)")


def list_candidates(container: Container, top: int, state: str | None) -> None:
    reviews = {row["person_id"]: row for row in container.candidate_review_service.list_rows()}
    rows = container.candidate_service.list_candidates("discovery")
    shown = 0
    for candidate in rows:
        review = reviews.get(candidate["id"], {})
        review_state = review.get("state", "unreviewed")
        if state and review_state != state:
            continue
        print(
            "\t".join(
                [
                    candidate["id"],
                    review_state,
                    candidate.get("source_bucket") or candidate.get("discovery_origin") or "",
                    candidate["name"],
                    str(round(candidate.get("score") or 0)),
                    candidate.get("primary_evidence_url") or "",
                ]
            )
        )
        shown += 1
        if shown >= top:
            break


def save_review(container: Container, args: argparse.Namespace) -> None:
    existing = container.candidate_reviews.get(args.person_id)
    state = args.command if args.command in {"approve", "reject"} else (
        args.state or (existing.state if existing else "pending")
    )
    review = container.candidate_review_service.review(
        person_id=args.person_id,
        state="approved" if state == "approve" else "rejected" if state == "reject" else state,
        why_now=args.why_now if args.why_now is not None else (existing.why_now if existing else ""),
        notes=args.notes if args.notes is not None else (existing.notes if existing else ""),
        source_bucket=(
            args.source_bucket
            if args.source_bucket is not None
            else (existing.source_bucket if existing else "")
        ),
        contactable=(
            args.contactable
            if args.contactable is not None
            else (existing.contactable if existing else False)
        ),
        primary_evidence_url=(
            args.evidence
            if args.evidence is not None
            else (existing.primary_evidence_url if existing else "")
        ),
        reviewer=args.reviewer if args.reviewer is not None else (existing.reviewer if existing else ""),
    )
    print(
        f"{review.state}: {review.person_id} "
        f"[{review.source_bucket or 'unclassified'}] updated {review.updated_at}"
    )


def add_review_arguments(parser: argparse.ArgumentParser, include_state: bool = False) -> None:
    parser.add_argument("person_id")
    if include_state:
        parser.add_argument("--state", choices=["pending", "approved", "rejected"])
    parser.add_argument("--why-now")
    parser.add_argument("--notes")
    parser.add_argument(
        "--source-bucket",
        choices=["github_cross_source", "provider_discovered", "manual_public"],
    )
    parser.add_argument("--evidence", help="Primary public evidence URL already stored on a signal.")
    parser.add_argument("--reviewer")
    contact_group = parser.add_mutually_exclusive_group()
    contact_group.add_argument("--contactable", action="store_true", dest="contactable")
    contact_group.add_argument("--not-contactable", action="store_false", dest="contactable")
    parser.set_defaults(contactable=None)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    list_parser = subparsers.add_parser("list", help="List candidates and review state.")
    list_parser.add_argument("--top", type=int, default=20)
    list_parser.add_argument("--state", choices=["unreviewed", "pending", "approved", "rejected"])
    export_parser = subparsers.add_parser("export", help="Write a Markdown review checklist.")
    export_parser.add_argument("--top", type=int, default=20)
    export_parser.add_argument("--output", type=Path)
    for command in ("approve", "reject", "update"):
        add_review_arguments(
            subparsers.add_parser(command, help=f"{command.title()} a persisted review."),
            include_state=command == "update",
        )
    args = parser.parse_args()
    container = Container()
    if args.command in {None, "list"}:
        list_candidates(container, getattr(args, "top", 20), getattr(args, "state", None))
    elif args.command == "export":
        output = args.output or container.settings.out_dir / "verify.md"
        export_checklist(container, args.top, output)
    else:
        save_review(container, args)


if __name__ == "__main__":
    main()
