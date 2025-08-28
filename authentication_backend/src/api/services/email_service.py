"""
Email service abstraction and SMTP implementation.
Supports sending plain text emails (sufficient for verification codes).
"""

from abc import ABC, abstractmethod
from email.message import EmailMessage
import smtplib
from typing import Optional


class EmailService(ABC):
    """Abstract interface for sending emails."""

    # PUBLIC_INTERFACE
    @abstractmethod
    def send_email(self, to_email: str, subject: str, body: str, *, reply_to: Optional[str] = None) -> None:
        """
        Send an email.

        :param to_email: Recipient email address.
        :param subject: Subject line.
        :param body: Plain text body content.
        :param reply_to: Optional reply-to email header.
        :raises RuntimeError: On failure to send.
        """
        raise NotImplementedError


class SmtpEmailService(EmailService):
    """SMTP-based email service (supports Gmail via app password)."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_email: str,
        from_name: str = "Auth System",
        use_tls: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls

    def _build_message(self, to_email: str, subject: str, body: str, reply_to: Optional[str]) -> EmailMessage:
        msg = EmailMessage()
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.set_content(body)
        return msg

    # PUBLIC_INTERFACE
    def send_email(self, to_email: str, subject: str, body: str, *, reply_to: Optional[str] = None) -> None:
        """Send a plain text email via SMTP."""
        msg = self._build_message(to_email, subject, body, reply_to)

        try:
            if self.use_tls:
                with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                    server.ehlo()
                    server.starttls()
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.host, self.port, timeout=30) as server:
                    server.ehlo()
                    server.login(self.username, self.password)
                    server.send_message(msg)
        except Exception as exc:
            raise RuntimeError(f"Failed to send email: {exc}") from exc
