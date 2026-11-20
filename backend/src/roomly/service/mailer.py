"""Transactional email: how the API asks for a verification or reset link to be sent.

``LogMailer`` (dev, tests) writes the link to the log. ``HttpMailer`` posts to the Cloudflare
mail Worker (``mail/``), signing each request with the secret both sides share. Nothing here
opens a socket other than that one HTTPS call, and nothing here is on the transaction path:
services send after their transaction commits, because a slow or failing mail service must not
hold a database transaction open or turn a sign-up into a 5xx.
"""

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

logger = logging.getLogger(__name__)

TEMPLATES = {"verify_email": "verify-email", "reset_password": "reset-password"}
SEND_TIMEOUT_SECONDS = 5.0


class MailError(Exception):
    """The mail service did not accept the message."""


@dataclass(frozen=True)
class Message:
    template: str          # a key of TEMPLATES
    to: str
    token: str             # the raw, single-use token; the Worker builds the link from it
    display_name: str | None = None


class Mailer(Protocol):
    def send(self, message: Message) -> None:
        """Raise ``MailError`` when the message was not accepted."""


class LogMailer:
    """Development mail: the link goes to the log instead of an inbox. Never use in production."""

    def __init__(self, app_url: str) -> None:
        self.app_url = app_url.rstrip("/")

    def send(self, message: Message) -> None:
        link = f"{self.app_url}/{TEMPLATES[message.template]}?token={quote(message.token)}"
        logger.info("mail %s to %s: %s", message.template, message.to, link)


class HttpMailer:
    """POST <url>/v1/send, signed as ``v1=hmac_sha256(secret, "<unix seconds>.<body>")``."""

    def __init__(self, url: str, secret: str, timeout: float = SEND_TIMEOUT_SECONDS) -> None:
        self.endpoint = url.rstrip("/") + "/v1/send"
        self.secret = secret.encode()
        self.timeout = timeout

    def send(self, message: Message) -> None:
        data: dict[str, str] = {"token": message.token}
        if message.display_name:
            data["display_name"] = message.display_name
        body = json.dumps({"template": message.template, "to": message.to, "data": data}).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(self.secret, timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
        request = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Roomly-Timestamp": timestamp,
                     "X-Roomly-Signature": f"v1={signature}"})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                status = response.status
        except urllib.error.HTTPError as exc:
            logger.warning("mail %s rejected: HTTP %s after %.2fs", message.template, exc.code,
                           time.monotonic() - started)
            raise MailError(f"mail service answered HTTP {exc.code}") from None
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("mail %s failed: %s after %.2fs", message.template, type(exc).__name__,
                           time.monotonic() - started)
            raise MailError(f"mail service unreachable: {type(exc).__name__}") from None
        logger.info("mail %s accepted: HTTP %s in %.2fs", message.template, status, time.monotonic() - started)


def build_mailer(mode: str, app_url: str, url: str | None, secret: str | None) -> Mailer:
    if mode == "log":
        return LogMailer(app_url)
    if mode == "http":
        assert url and secret, "http mail needs ROOMLY_MAIL_URL and ROOMLY_MAIL_SECRET"
        return HttpMailer(url, secret)
    raise ValueError(f"ROOMLY_MAIL must be 'log' or 'http', got {mode!r}")
