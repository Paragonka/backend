from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class AppUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._session: AsyncSession | None = None
        self._depth: int = 0

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            # Auto-open for read-after-write in same request: after a
            # service's `async with self.uow` commits and closes (depth 0,
            # _session=None), a subsequent read in the same handler (e.g.
            # get_order -> change_status -> get_items) would otherwise raise
            # "session is not open". Auto-opening creates a fresh session for
            # the next read without requiring the handler to manage transactions.
            self.open()

        # open() is idempotent and guarantees a non-None session.
        assert self._session is not None  # noqa: S101
        return self._session

    @session.setter
    def session(self, value: AsyncSession | None) -> None:
        self._session = value

    @property
    def users(self):
        from app.features.users.repository import UserRepository

        return UserRepository(self.session)

    @property
    def orgs(self):
        from app.features.orgs.repository import OrgRepository

        return OrgRepository(self.session)

    @property
    def invites(self):
        from app.features.orgs.repository import InviteRepository

        return InviteRepository(self.session)

    @property
    def clients(self):
        from app.features.clients.repository import ClientRepository

        return ClientRepository(self.session)

    @property
    def products(self):
        from app.features.products.repository import ProductRepository

        return ProductRepository(self.session)

    @property
    def eav_attributes(self):
        from app.features.eav.repository import EavAttributeRepository

        return EavAttributeRepository(self.session)

    @property
    def orders(self):
        from app.features.orders.repository import OrderRepository

        return OrderRepository(self.session)

    @property
    def order_items(self):
        from app.features.orders.repository import OrderItemRepository

        return OrderItemRepository(self.session)

    @property
    def writeoffs(self):
        from app.features.orders.repository import WriteOffRepository

        return WriteOffRepository(self.session)

    @property
    def receipts(self):
        from app.features.receipts.repository import ReceiptRepository

        return ReceiptRepository(self.session)

    @property
    def receipt_items(self):
        from app.features.receipts.repository import ReceiptItemRepository

        return ReceiptItemRepository(self.session)

    @property
    def refresh_sessions(self):
        from app.features.auth.repository import RefreshSessionRepository

        return RefreshSessionRepository(self.session)

    @property
    def consents(self):
        from app.features.legal.repository import UserConsentRepository

        return UserConsentRepository(self.session)

    def open(self) -> None:
        """Create the session if it does not exist yet (idempotent).

        Does NOT enter a managed transaction block (no depth increment):
        used by read-only consumers that never wrap work in `async with`.
        """

        if self._session is None:
            self._session = self._session_factory()

    async def aclose(self) -> None:
        """Discard the session if no transaction block is active.

        Read-only request paths open a session without ever entering a
        transaction block; this closes such a session without committing.
        No-op when a block is active or the session was already committed
        and closed by __aexit__.
        """

        if self._depth > 0 or self._session is None:
            return

        try:
            await self._session.rollback()
        finally:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "AppUnitOfWork":
        # Reuse an existing session (e.g. opened via .open() by get_uow)
        # instead of replacing it - otherwise the pre-opened session would leak.
        self.open()
        self._depth += 1

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self._depth -= 1

        if self._depth == 0:
            # Use _session directly to avoid auto-open side-effect
            session = self._session

            if session is None:
                return

            try:
                if exc_type:
                    await session.rollback()
                else:
                    await session.commit()
            finally:
                await session.close()
                self._session = None
