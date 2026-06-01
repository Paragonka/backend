from uuid import UUID

from sqlalchemy import select

from app.features.legal.models import UserConsent


class UserConsentRepository:
    def __init__(self, session):
        self.session = session

    async def add(self, consent: UserConsent) -> UserConsent:
        self.session.add(consent)
        await self.session.flush()

        return consent

    async def get_by_user_and_type(
        self, user_id: str | UUID, consent_type: str
    ) -> UserConsent | None:
        result = await self.session.execute(
            select(UserConsent).where(
                UserConsent.user_id == str(user_id),
                UserConsent.consent_type == consent_type,
            )
        )

        return result.scalars().first()

    async def has_consent(self, user_id: str | UUID, consent_type: str) -> bool:
        return await self.get_by_user_and_type(user_id, consent_type) is not None
