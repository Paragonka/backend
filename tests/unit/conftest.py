from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.uow import AppUnitOfWork


@pytest.fixture
def mock_session():
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.execute.return_value = MagicMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_uow(mock_session):
    uow = MagicMock(spec=AppUnitOfWork)
    uow.session = mock_session
    return uow
