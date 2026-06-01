from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.base_model import Base, TimestampMixin


class EavAttribute(TimestampMixin, Base):
    __tablename__ = "eav_attributes"
    __table_args__ = (
        Index("uq_eav_org_entity_code", "org_id", "entity_code", "code", unique=True),
    )

    org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    entity_code: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    field_type: Mapped[str] = mapped_column(String(50))
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    default_value: Mapped[str] = mapped_column(Text, default="")
