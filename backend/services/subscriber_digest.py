"""Build and deliver personalized, never-repeat subscriber digests."""

import html
from datetime import datetime, timezone
from urllib.parse import quote

from backend.db.repositories.subscriptions import (
    DigestSendRepository,
    SubscriberRepository,
)
from backend.digest.sender import EmailMessage, EmailSender
from backend.domain.subscriber import Subscriber
from backend.services.candidate_service import CandidateService


class SubscriberDigestService:
    def __init__(
        self,
        subscribers: SubscriberRepository,
        sends: DigestSendRepository,
        candidates: CandidateService,
        sender: EmailSender,
        public_base_url: str,
        size: int = 10,
    ):
        self.subscribers = subscribers
        self.sends = sends
        self.candidates = candidates
        self.sender = sender
        self.public_base_url = public_base_url.rstrip("/")
        self.size = size

    def build(self, subscriber: Subscriber) -> tuple[EmailMessage, list[str]]:
        sent_ids = self.sends.sent_person_ids(subscriber.id)
        pool = [
            candidate
            for candidate in self.candidates.list_candidates("discovery")
            if candidate["id"] not in sent_ids
        ]
        pool.sort(key=lambda candidate: self._preference_rank(candidate, subscriber), reverse=True)
        picks = pool[: self.size]
        today = datetime.now(timezone.utc).date().isoformat()
        subject = f"Signal Scout — {len(picks)} people to know ({today})"
        return (
            EmailMessage(
                subject=subject,
                html=self._render_html(subscriber, picks, today),
                text=self._render_text(subscriber, picks, today),
            ),
            [candidate["id"] for candidate in picks],
        )

    def deliver(self, subscriber: Subscriber, dry_run: bool = False) -> dict:
        message, person_ids = self.build(subscriber)
        if not person_ids:
            return {
                "email": subscriber.email,
                "status": "empty",
                "candidate_count": 0,
            }
        if dry_run:
            return {
                "email": subscriber.email,
                "status": "preview",
                "candidate_count": len(person_ids),
                "subject": message.subject,
                "html": message.html,
                "text": message.text,
            }
        receipt = self.sender.send(message, subscriber.email)
        if receipt.get("sent"):
            self.sends.record_many(subscriber.id, person_ids, receipt.get("id"))
            status = "sent"
        elif receipt.get("preview_only"):
            status = "preview"
        else:
            status = "failed"
        return {
            "email": subscriber.email,
            "status": status,
            "candidate_count": len(person_ids),
            "receipt": receipt,
        }

    def run_due(
        self,
        dry_run: bool = False,
        recipient: str | None = None,
        now: datetime | None = None,
    ) -> dict:
        run_at = now or datetime.now(timezone.utc)
        self.candidates.rescore_all()
        due = self.subscribers.active(email=recipient)
        if recipient is None:
            due = [
                subscriber
                for subscriber in due
                if subscriber.frequency == "daily"
                or (subscriber.frequency == "weekly" and run_at.weekday() == 0)
            ]
        results = [self.deliver(subscriber, dry_run=dry_run) for subscriber in due]
        return {
            "dry_run": dry_run,
            "run_at": run_at.isoformat(timespec="seconds"),
            "subscriber_count": len(results),
            "sent_count": sum(result["status"] == "sent" for result in results),
            "results": results,
        }

    @staticmethod
    def _preference_rank(candidate: dict, subscriber: Subscriber) -> tuple[int, float]:
        interests = str(subscriber.preferences.get("signal_interests", "")).lower().split()
        haystack = " ".join(
            [
                str(candidate.get("area") or ""),
                str(candidate.get("thesis") or ""),
                *[
                    f"{signal.get('type', '')} {signal.get('summary', '')}"
                    for signal in candidate.get("top_signals", [])
                ],
            ]
        ).lower()
        matches = sum(term.strip(",.;") in haystack for term in interests if len(term) > 2)
        return matches, float(candidate.get("score") or 0)

    def _feedback_url(self, subscriber: Subscriber, person_id: str, vote: str) -> str:
        return (
            f"{self.public_base_url}/api/digest/feedback"
            f"?token={quote(subscriber.unsubscribe_token, safe='')}"
            f"&person_id={quote(person_id, safe='')}&vote={vote}"
        )

    def _unsubscribe_url(self, subscriber: Subscriber) -> str:
        return (
            f"{self.public_base_url}/api/digest/unsubscribe"
            f"?token={quote(subscriber.unsubscribe_token, safe='')}"
        )

    def _render_html(self, subscriber: Subscriber, picks: list[dict], today: str) -> str:
        esc = html.escape
        blocks: list[str] = []
        for candidate in picks:
            person_id = candidate["id"]
            signals = candidate.get("top_signals") or []
            signal_items = "".join(
                f"<li>{esc(signal.get('summary') or signal.get('type') or 'Signal recorded')}</li>"
                for signal in signals
            )
            links = "".join(
                f'<a href="{esc(url, quote=True)}" style="color:#60652b;margin-right:14px">{esc(label.title())}</a>'
                for label, url in (candidate.get("contact_links") or {}).items()
                if label in {"linkedin", "x", "github"} and url
            )
            context = " · ".join(
                part
                for part in [
                    candidate.get("school"),
                    candidate.get("current_location") or candidate.get("origin_location"),
                ]
                if part
            )
            description = (
                candidate.get("thesis")
                or candidate.get("why_now")
                or candidate.get("area")
                or "Showing multiple early signals worth a closer look."
            )
            up_url = self._feedback_url(subscriber, person_id, "up")
            down_url = self._feedback_url(subscriber, person_id, "down")
            blocks.append(
                f"""
                <section style="background:#fffdf7;border:1px solid #d8d4c4;border-radius:6px;padding:18px;margin:0 0 16px">
                  <div style="float:right;color:#60652b;font:700 20px ui-monospace,monospace">{float(candidate.get("score") or 0):.0f}</div>
                  <h2 style="font-size:21px;margin:0 36px 4px 0">{esc(candidate["name"])}</h2>
                  <div style="color:#716d5e;font:12px ui-monospace,monospace">{esc(context)}</div>
                  <p style="font-size:15px;line-height:1.45;margin:12px 0">{esc(description)}</p>
                  <div style="font-size:13px;line-height:1.5"><strong>Triggering signals</strong><ul style="padding-left:20px;margin:6px 0 12px">{signal_items}</ul></div>
                  <div style="font:12px ui-monospace,monospace">{links}</div>
                  <div style="border-top:1px solid #e4e0d2;margin-top:14px;padding-top:10px;font-size:13px">
                    Useful?
                    <a href="{esc(up_url, quote=True)}" style="text-decoration:none;margin-left:8px">👍 Yes</a>
                    <a href="{esc(down_url, quote=True)}" style="text-decoration:none;margin-left:12px">👎 No</a>
                  </div>
                </section>"""
            )
        unsubscribe = esc(self._unsubscribe_url(subscriber), quote=True)
        return f"""<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#f5f3ec;color:#1c1b16;font-family:Georgia,'Times New Roman',serif">
  <main style="max-width:620px;margin:0 auto;padding:24px 14px">
    <h1 style="font-size:27px;margin:0">Signal Scout</h1>
    <p style="color:#60652b;font:11px ui-monospace,monospace;text-transform:uppercase;letter-spacing:1px;margin:6px 0 22px">{len(picks)} people · {today}</p>
    {''.join(blocks)}
    <footer style="text-align:center;color:#817d6e;font:11px ui-monospace,monospace;padding:12px">
      You receive this {esc(subscriber.frequency)} digest.
      <a href="{unsubscribe}" style="color:#60652b">Unsubscribe</a>
    </footer>
  </main>
</body></html>"""

    def _render_text(self, subscriber: Subscriber, picks: list[dict], today: str) -> str:
        lines = [f"SIGNAL SCOUT — {len(picks)} people — {today}", ""]
        for index, candidate in enumerate(picks, 1):
            context = " · ".join(
                part
                for part in [
                    candidate.get("school"),
                    candidate.get("current_location") or candidate.get("origin_location"),
                ]
                if part
            )
            description = (
                candidate.get("thesis")
                or candidate.get("why_now")
                or candidate.get("area")
                or "Showing multiple early signals worth a closer look."
            )
            lines.extend([f"{index}. {candidate['name']} ({float(candidate.get('score') or 0):.0f})"])
            if context:
                lines.append(context)
            lines.append(description)
            lines.append("Triggering signals:")
            for signal in candidate.get("top_signals") or []:
                lines.append(f"- {signal.get('summary') or signal.get('type') or 'Signal recorded'}")
            for label, url in (candidate.get("contact_links") or {}).items():
                if label in {"linkedin", "x", "github"} and url:
                    lines.append(f"{label.title()}: {url}")
            lines.append(f"Useful: {self._feedback_url(subscriber, candidate['id'], 'up')}")
            lines.append(f"Not useful: {self._feedback_url(subscriber, candidate['id'], 'down')}")
            lines.append("")
        lines.append(f"Unsubscribe: {self._unsubscribe_url(subscriber)}")
        return "\n".join(lines)
