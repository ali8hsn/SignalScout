"""EmailSender interface. Real sending (Resend) is intentionally NOT wired —
the digest is preview/generate only (locked decision). Swap in a ResendSender
later without touching DigestGenerator."""

from abc import ABC, abstractmethod

from backend.domain.digest import Digest


class EmailSender(ABC):
    @abstractmethod
    def send(self, digest: Digest, to: str) -> dict:
        """Returns a delivery receipt dict."""


class NoopSender(EmailSender):
    def send(self, digest: Digest, to: str) -> dict:
        return {
            "sent": False,
            "preview_only": True,
            "to": to,
            "subject": digest.subject,
            "note": "Email sending is stubbed (NoopSender). Wire ResendSender to go live.",
        }
