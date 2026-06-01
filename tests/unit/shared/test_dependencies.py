from unittest.mock import AsyncMock, MagicMock

import pytest

from app.shared.exceptions import OrgAccessDenied, ValidationException

pytestmark = pytest.mark.usefixtures("mock_uow")

VALID_UUID = "00000000-0000-0000-0000-000000000001"


class TestVerifyOrgAccess:
    async def test_user_in_org_grants_access(self, mock_uow):
        from app.shared.dependencies import verify_org_access

        result = await verify_org_access(
            VALID_UUID, user=MagicMock(id="user-1"), uow=mock_uow
        )

        assert result == VALID_UUID

    async def test_user_not_in_org_raises_403(self, mock_uow):
        from app.shared.dependencies import verify_org_access

        mock_uow.session.execute = AsyncMock()
        mock_uow.session.execute.return_value.scalar_one_or_none = MagicMock(
            return_value=None
        )

        with pytest.raises(OrgAccessDenied) as exc:
            await verify_org_access(
                VALID_UUID, user=MagicMock(id="other-user"), uow=mock_uow
            )

        assert exc.value.status_code == 403

    async def test_invalid_org_id_raises_422(self, mock_uow):
        from app.shared.dependencies import verify_org_access

        with pytest.raises(ValidationException) as exc:
            await verify_org_access(
                "non-existent-org", user=MagicMock(id="user-1"), uow=mock_uow
            )

        assert exc.value.status_code == 422
