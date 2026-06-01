from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

# ISO-4217 currency codes allowed for organization settings.
ALLOWED_CURRENCIES = ("RUB", "PLN", "USD", "EUR", "BYN", "KZT", "UAH")


class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    timezone: str = Field(default="UTC", max_length=64)


class OrgUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class OrgResponse(BaseModel):
    id: UUID
    name: str
    owner_id: UUID
    timezone: str

    model_config = {"from_attributes": True}


class OrgSettingsUpdate(BaseModel):
    currency: str = "PLN"

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, v: str) -> str:
        if v not in ALLOWED_CURRENCIES:
            raise ValueError(f"currency must be one of {ALLOWED_CURRENCIES}")
        return v


class OrgSettingsResponse(BaseModel):
    currency: str


class InviteCreate(BaseModel):
    email: EmailStr


class InviteCreatedResponse(BaseModel):
    invite_id: UUID
    token: str
    expires_at: datetime | None


class InviteListItemResponse(BaseModel):
    invite_id: UUID
    email: str
    token: str
    expires_at: datetime | None


class AcceptInviteRequest(BaseModel):
    token: str = Field(..., min_length=1)


class AcceptInviteResponse(BaseModel):
    org_id: UUID
    org_name: str
    role: str


class MemberResponse(BaseModel):
    user_id: UUID
    email: str
    full_name: str
    role: str
