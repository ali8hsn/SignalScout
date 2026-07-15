"""Short-lived, action-scoped tokens for digest links."""

import base64
import hashlib
import hmac
import json
import time


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


class EmailActionSigner:
    def __init__(self, secret: str, ttl_seconds: int = 30 * 24 * 60 * 60):
        self.secret = secret
        self.ttl_seconds = ttl_seconds

    def issue(
        self,
        subscriber_id: str,
        action: str,
        person_id: str = "",
        vote: str = "",
    ) -> str:
        if not self.secret:
            return ""
        payload = _encode(
            json.dumps(
                {
                    "sub": subscriber_id,
                    "action": action,
                    "person": person_id,
                    "vote": vote,
                    "exp": int(time.time()) + self.ttl_seconds,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
        )
        return f"{payload}.{self._sign(payload)}"

    def verify(
        self,
        token: str,
        action: str,
        person_id: str = "",
        vote: str = "",
    ) -> str | None:
        if not self.secret:
            return None
        try:
            payload, supplied = token.split(".", 1)
            if not hmac.compare_digest(supplied, self._sign(payload)):
                return None
            data = json.loads(_decode(payload))
            valid = (
                data["action"] == action
                and data.get("person", "") == person_id
                and data.get("vote", "") == vote
                and int(data["exp"]) >= int(time.time())
            )
            return str(data["sub"]) if valid else None
        except (ValueError, KeyError, TypeError, json.JSONDecodeError):
            return None

    def _sign(self, payload: str) -> str:
        return _encode(
            hmac.new(self.secret.encode(), payload.encode(), hashlib.sha256).digest()
        )
