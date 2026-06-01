from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, SecretStr, field_validator


def _normalize_email(value: str) -> str:
    # Emails are stored and compared case-insensitively: the canonical form
    # is lower case (e.g. "Sovwva7@gmail.com" -> "sovwva7@gmail.com").
    return value.strip().lower()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: SecretStr = Field(..., min_length=8)
    full_name: str = Field(..., min_length=2, max_length=255)
    # Consent is part of registration; later legal changes are handled by
    # advance email notice and do not block write operations.
    consent_to_processing: Literal[True]

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: SecretStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ChangePasswordRequest(BaseModel):
    current_password: SecretStr
    new_password: SecretStr = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return _normalize_email(value)


class ResetPasswordRequest(BaseModel):
    token: str
    password: SecretStr = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    # S105 - OAuth2 token_type constant, not a password
    token_type: str = "bearer"  # noqa: S105
    user: Optional["UserResponse"] = None


# E402 - late import to avoid a circular dependency
from app.features.users.schemas import UserResponse  # noqa: E402

TokenResponse.model_rebuild()
