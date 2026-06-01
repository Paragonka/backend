from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base_model import Base, TimestampMixin

ORG_DEFAULT_SETTINGS: dict[str, str] = {"currency": "PLN"}

ROLE_OWNER = "owner"
ROLE_MEMBER = "member"


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")

    owner = relationship("User", backref="owned_organizations")
    settings_list = relationship(
        "OrganizationSetting", back_populates="org", lazy="selectin"
    )


class OrganizationSetting(Base):
    __tablename__ = "organization_settings"

    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(String(1024))

    org = relationship("Organization", back_populates="settings_list")


class UserOrg(Base):
    __tablename__ = "user_orgs"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ROLE_MEMBER, server_default=ROLE_MEMBER
    )


class Invite(TimestampMixin, Base):
    __tablename__ = "invites"
    __table_args__ = (
        # One active (unused) invite per (org, email); a used invite no longer
        # blocks creating a new one.
        Index(
            "uq_invites_org_email_active",
            "org_id",
            "email",
            unique=True,
            postgresql_where=text("used_at IS NULL"),
        ),
    )

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"))
    email: Mapped[str] = mapped_column(String(255))
    token: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
