from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.legal.models import UserConsent

logger = get_logger(__name__)

TYPE_COOKIE = "cookie"
TYPE_POLICY = "policy"


class LegalService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    async def record_consent(
        self,
        user_id: str,
        consent_type: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> UserConsent:
        async with self.uow:
            consent = UserConsent(
                user_id=user_id,
                consent_type=consent_type,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            self.uow.session.add(consent)
            await self.uow.session.flush()

            # Consent acceptance is a compliance-relevant event: keep an audit
            # trail of who accepted which policy and from where.
            logger.info(
                "consent_recorded",
                user_id=str(user_id),
                consent_type=consent_type,
                ip_address=ip_address,
            )

            return consent

    async def has_policy_consent(self, user_id: str) -> bool:
        from app.features.legal.repository import UserConsentRepository

        repo = UserConsentRepository(self.uow.session)

        return await repo.has_consent(user_id, TYPE_POLICY)
