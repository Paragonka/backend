from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.core.log import get_logger
from app.core.uow import AppUnitOfWork
from app.features.clients.models import Client
from app.features.eav.models import EavAttribute
from app.features.eav.repository import EavAttributeRepository
from app.features.orders.models import Order
from app.features.products.models import Product
from app.shared.constants import EAV_FIELD_TYPE_STRING, EAV_FIELD_TYPES
from app.shared.exceptions import ConflictException, EavValidationError

logger = get_logger(__name__)

_ORPHAN_VALUE_MODELS = {"client": Client, "product": Product, "order": Order}


class EavAttributeService:
    def __init__(self, uow: AppUnitOfWork):
        self.uow = uow

    @property
    def _attributes(self) -> EavAttributeRepository:
        return EavAttributeRepository(self.uow.session)

    async def create_attribute(
        self,
        org_id: str,
        entity_code: str,
        code: str,
        name: str,
        field_type: str = EAV_FIELD_TYPE_STRING,
        is_required: bool = False,
        default_value: str = "",
    ) -> EavAttribute:
        if field_type not in EAV_FIELD_TYPES:
            raise EavValidationError(
                code,
                f"Invalid field_type: {field_type}. "
                f"Valid: {', '.join(sorted(EAV_FIELD_TYPES))}",
            )

        async with self.uow:
            existing = await self._attributes.get_by_code(org_id, entity_code, code)

            if existing:
                raise ConflictException(
                    f"EAV attribute with code '{code}' already exists for {entity_code}"
                )

            attr = EavAttribute(
                org_id=org_id,
                entity_code=entity_code,
                code=code,
                name=name,
                field_type=field_type,
                is_required=is_required,
                default_value=default_value,
            )

            try:
                created = await self._attributes.add(attr)
            except IntegrityError as exc:
                raise ConflictException(
                    f"EAV attribute with code '{code}' already exists for {entity_code}"
                ) from exc

            logger.info(
                "eav_attribute_created",
                attr_id=str(created.id),
                org_id=org_id,
                entity_code=entity_code,
                code=code,
            )
            return created

    async def update_attribute(
        self,
        attr_id: str | UUID,
        org_id: str | UUID,
        name: str | None = None,
        field_type: str | None = None,
        is_required: bool | None = None,
        default_value: str | None = None,
    ) -> EavAttribute | None:
        async with self.uow:
            attr = await self._attributes.get_by_id_and_org(attr_id, org_id)

            if not attr:
                return None

            if field_type is not None:
                if field_type not in EAV_FIELD_TYPES:
                    raise EavValidationError(
                        attr.code,
                        f"Invalid field_type: {field_type}. "
                        f"Valid: {', '.join(sorted(EAV_FIELD_TYPES))}",
                    )

                attr.field_type = field_type

            if name is not None:
                attr.name = name

            if is_required is not None:
                attr.is_required = is_required

            if default_value is not None:
                attr.default_value = default_value

            await self.uow.session.flush()
            await self.uow.session.refresh(attr)

            logger.info(
                "eav_attribute_updated",
                attr_id=str(attr.id),
                org_id=org_id,
                entity_code=attr.entity_code,
                code=attr.code,
            )

            return attr

    async def get_by_entity_code(
        self, org_id: str | UUID, entity_code: str
    ) -> list[EavAttribute]:
        return await self._attributes.get_by_entity_code(org_id, entity_code)

    async def get_all(self, org_id: str | UUID) -> list[EavAttribute]:
        return await self._attributes.get_all(org_id)

    async def get_attribute(self, attr_id: str | UUID) -> EavAttribute | None:
        return await self._attributes.get_by_id(attr_id)

    async def delete_attribute(
        self, attr_id: str | UUID, org_id: str | UUID | None = None
    ) -> bool:
        """When org_id is set -> composite lookup (org_id, id), otherwise bare id."""

        async with self.uow:
            if org_id is not None:
                attr = await self._attributes.get_by_id_and_org(attr_id, org_id)
            else:
                attr = await self._attributes.get_by_id(attr_id)

            if not attr:
                return False

            model = _ORPHAN_VALUE_MODELS.get(attr.entity_code)

            if model is not None:
                await self.uow.session.execute(
                    update(model)
                    .where(
                        model.org_id == str(attr.org_id),
                        model.custom_fields.has_key(attr.code),
                    )
                    .values(custom_fields=model.custom_fields.op("-")(attr.code))
                )

            await self._attributes.delete(attr)

            logger.info(
                "eav_attribute_deleted",
                attr_id=str(attr.id),
                org_id=org_id,
                entity_code=attr.entity_code,
                code=attr.code,
            )

            return True

    @staticmethod
    def validate_custom_fields(
        custom_fields: dict | None, attributes: list[EavAttribute]
    ) -> None:
        if not custom_fields:
            custom_fields = {}

        known_codes = {attr.code for attr in attributes}
        unknown_codes = sorted(set(custom_fields.keys()) - known_codes)

        if unknown_codes:
            raise EavValidationError(
                unknown_codes[0],
                f"Unknown attribute code(s): {', '.join(unknown_codes)}",
            )

        for attr in attributes:
            value = custom_fields.get(attr.code)

            if attr.is_required and (value is None or value == ""):
                raise EavValidationError(attr.code, f"Field '{attr.name}' is required")

            if value is not None and value != "":
                EavAttributeService._validate_field_type(
                    attr.code, attr.name, attr.field_type, value
                )

    @staticmethod
    def _validate_field_type(
        code: str, name: str, field_type: str, value: object
    ) -> None:
        if field_type == "string":
            if not isinstance(value, str):
                raise EavValidationError(code, f"Field '{name}' must be a string")
        elif field_type == "text":
            if not isinstance(value, str):
                raise EavValidationError(code, f"Field '{name}' must be text")
        elif field_type == "number":
            try:
                Decimal(str(value))
            except (ValueError, TypeError, ArithmeticError) as exc:
                raise EavValidationError(
                    code, f"Field '{name}' must be a number"
                ) from exc
        elif field_type == "boolean":
            if not isinstance(value, bool):
                raise EavValidationError(code, f"Field '{name}' must be a boolean")
        elif field_type == "date":
            EavAttributeService._validate_date(code, name, value)

    @staticmethod
    def _validate_date(code: str, name: str, value: object) -> None:
        if not isinstance(value, str):
            raise EavValidationError(
                code, f"Field '{name}' must be a date string (YYYY-MM-DD)"
            )

        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError as exc:
            raise EavValidationError(
                code, f"Field '{name}' must be a valid date (YYYY-MM-DD)"
            ) from exc
