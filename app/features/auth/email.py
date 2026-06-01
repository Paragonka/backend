"""Email sending abstraction for authentication and legal notifications."""

from abc import ABC, abstractmethod

from app.core.config import settings


class EmailSender(ABC):
    @abstractmethod
    async def send_password_reset(self, to_email: str, reset_url: str) -> None: ...

    @abstractmethod
    async def send_legal_update(
        self,
        to_email: str,
        effective_date: str,
        terms_url: str,
        privacy_url: str,
    ) -> None: ...


class DevEmailSender(EmailSender):
    """Dev: no-op, so local tests never send real messages."""

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        pass

    async def send_legal_update(
        self,
        to_email: str,
        effective_date: str,
        terms_url: str,
        privacy_url: str,
    ) -> None:
        pass


class SmtpEmailSender(EmailSender):
    """Prod: sends the reset link by email via SMTP."""

    def __init__(self, host: str, port: int, user: str, password: str, from_email: str):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email

    async def _send(self, message) -> None:
        import aiosmtplib

        await aiosmtplib.send(
            message,
            hostname=self.host,
            port=self.port,
            start_tls=True,
            username=self.user,
            password=self.password,
        )

    async def send_password_reset(self, to_email: str, reset_url: str) -> None:
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Subject"] = "Paragonka CRM - Reset your password"
        msg.set_content(
            f"Click the link below to reset your password:\n\n{reset_url}\n\n"
            f"This link expires in 30 minutes.\n"
            f"If you didn't request this, ignore this email."
        )

        await self._send(msg)

    async def send_legal_update(
        self,
        to_email: str,
        effective_date: str,
        terms_url: str,
        privacy_url: str,
    ) -> None:
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = self.from_email
        msg["To"] = to_email
        msg["Subject"] = "Paragonka CRM - Important legal update"
        msg.set_content(
            "We are notifying you about material changes to the Paragonka CRM "
            f"legal documents. The new version takes effect on {effective_date}.\n\n"
            f"Terms of Use: {terms_url}\n"
            f"Privacy Policy: {privacy_url}\n\n"
            "If you do not agree with the changes, you may stop using the Service "
            "and delete your account before the effective date."
        )

        await self._send(msg)


def create_email_sender() -> EmailSender:
    """Factory: SmtpEmailSender if SMTP is configured, otherwise DevEmailSender."""

    if settings.smtp_host:
        return SmtpEmailSender(
            host=settings.smtp_host,
            port=settings.smtp_port,
            user=settings.smtp_user,
            password=settings.smtp_password.get_secret_value(),
            from_email=settings.from_email,
        )

    return DevEmailSender()
