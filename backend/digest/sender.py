"""Email transport with a keyless-safe Resend implementation."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class EmailMessage:
    subject: str
    html: str
    text: str


class EmailSender(ABC):
    @abstractmethod
    def send(self, message: EmailMessage, to: str) -> dict:
        """Returns a delivery receipt dict."""


class NoopSender(EmailSender):
    def send(self, message: EmailMessage, to: str) -> dict:
        return {
            "sent": False,
            "preview_only": True,
            "to": to,
            "subject": message.subject,
            "note": "Email preview generated; no provider delivery was attempted.",
        }


class ResendSender(EmailSender):
    API_URL = "https://api.resend.com/emails"

    def __init__(
        self,
        api_key: str,
        from_email: str,
        timeout_seconds: int = 15,
        session: requests.Session | None = None,
    ):
        self.api_key = api_key
        self.from_email = from_email
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.from_email)

    def send(self, message: EmailMessage, to: str) -> dict:
        if not self.configured:
            return NoopSender().send(message, to)
        try:
            response = self.session.post(
                self.API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": self.from_email,
                    "to": [to],
                    "subject": message.subject,
                    "html": message.html,
                    "text": message.text,
                },
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            return {
                "sent": False,
                "preview_only": False,
                "to": to,
                "subject": message.subject,
                "error": "Email provider rejected or could not process the request.",
            }
        return {
            "sent": True,
            "preview_only": False,
            "to": to,
            "subject": message.subject,
            "provider": "resend",
            "id": payload.get("id"),
        }
