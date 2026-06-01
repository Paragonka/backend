from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_uow(mock_uow):
    mock_uow.__aenter__ = AsyncMock(return_value=mock_uow)
    mock_uow.__aexit__ = AsyncMock(return_value=None)
    return mock_uow
