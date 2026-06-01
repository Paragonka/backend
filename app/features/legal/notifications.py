"""Delivery of advance notices about material legal-document changes."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.features.auth.email import EmailSender, create_email_sender
from app.features.legal.models import LegalNotification
from app.features.users.models import User

logger = structlog.get_logger(__name__)

MINIMUM_NOTICE = timedelta(days=14)


@dataclass(frozen=True)
class LegalNotificationResult:
    sent: int = 0
    skipped: int = 0
    failed: int = 0


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


async def send_legal_update_notifications(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    policy_version: str,
    effective_at: datetime,
    terms_url: str,
    privacy_url: str,
    sender: EmailSender | None = None,
) -> LegalNotificationResult:
    """Send one notice per account and record the delivery outcome.

    The function is intended to be called by the release/operations command
    when a new legal version is published. It refuses dates with less than the
    required 14-day notice and is idempotent for successful deliveries.
    """

    effective_at = _as_utc(effective_at)

    if effective_at < datetime.now(UTC) + MINIMUM_NOTICE:
        raise ValueError("The effective date must be at least 14 days from now")

    sender = sender or create_email_sender()

    async with session_factory() as session:
        users = (await session.execute(select(User.id, User.email))).all()

    sent = skipped = failed = 0

    for user_id, email in users:
        async with session_factory() as session:
            delivery = await session.scalar(
                select(LegalNotification).where(
                    LegalNotification.user_id == str(user_id),
                    LegalNotification.policy_version == policy_version,
                )
            )

            if delivery and delivery.status == "sent":
                skipped += 1

                continue

        try:
            await sender.send_legal_update(
                email,
                effective_at.date().isoformat(),
                terms_url,
                privacy_url,
            )
        except Exception as exc:  # delivery must be recorded
            failed += 1
            await _record_delivery(
                session_factory,
                user_id=str(user_id),
                email=email,
                policy_version=policy_version,
                effective_at=effective_at,
                status="failed",
                error=str(exc),
            )
            logger.warning(
                "legal_update_email_failed",
                user_id=str(user_id),
                error=str(exc),
            )
        else:
            sent += 1
            await _record_delivery(
                session_factory,
                user_id=str(user_id),
                email=email,
                policy_version=policy_version,
                effective_at=effective_at,
                status="sent",
                error=None,
            )

    logger.info(
        "legal_update_notifications_done",
        policy_version=policy_version,
        sent=sent,
        skipped=skipped,
        failed=failed,
    )

    return LegalNotificationResult(sent=sent, skipped=skipped, failed=failed)


async def _record_delivery(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    user_id: str,
    email: str,
    policy_version: str,
    effective_at: datetime,
    status: str,
    error: str | None,
) -> None:
    async with session_factory() as session:
        delivery = await session.scalar(
            select(LegalNotification).where(
                LegalNotification.user_id == user_id,
                LegalNotification.policy_version == policy_version,
            )
        )

        if delivery is None:
            delivery = LegalNotification(
                user_id=user_id,
                email=email,
                policy_version=policy_version,
                effective_at=effective_at,
                status=status,
                error=error,
                sent_at=datetime.now(UTC) if status == "sent" else None,
            )
            session.add(delivery)
        else:
            delivery.email = email
            delivery.effective_at = effective_at
            delivery.status = status
            delivery.error = error
            delivery.sent_at = datetime.now(UTC) if status == "sent" else None

        await session.commit()
