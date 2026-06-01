"""Reproduce the register -> immediate-request race on a REAL uvicorn server.

ASGITransport cannot reproduce the timing: it awaits the full ASGI lifecycle
(including dependency teardown/commit) before returning. A real server sends
the response and serves the next keep-alive request while teardown-commit is
still pending.

Usage: .venv/bin/python scripts/check_register_race.py [N]

Creates N users (racecheck-<ts>-<i>@example.test) in the configured DB,
prints how many immediate follow-up GET /api/v1/orgs returned 401, then
cleans up the created rows.
"""

import asyncio
import contextlib
import datetime as dt
import socket
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
import uvicorn


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))

        return s.getsockname()[1]


async def _cleanup(emails: list[str]) -> None:
    from sqlalchemy import delete, select

    from app.core.database import AsyncSessionLocal
    from app.features.auth.models import RefreshSession
    from app.features.legal.models import UserConsent
    from app.features.users.models import User

    if not emails:
        return

    async with AsyncSessionLocal() as session:
        ids = (
            await session.scalars(select(User.id).where(User.email.in_(emails)))
        ).all()

        if not ids:
            return

        for model in (RefreshSession, UserConsent):
            await session.execute(delete(model).where(model.user_id.in_(ids)))

        await session.execute(delete(User).where(User.email.in_(emails)))
        await session.commit()


async def main(n: int) -> int:
    from app.main import app

    port = _free_port()
    config = uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="warning", loop="asyncio"
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    while not server.started:
        await asyncio.sleep(0.05)

    ts = dt.datetime.now(dt.UTC).strftime("%Y%m%d%H%M%S")
    emails = [f"racecheck-{ts}-{i}@example.com" for i in range(n)]
    unauthorized = 0
    failures: list[str] = []

    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=10.0) as http:
            # keep-alive connection reused across the whole loop
            for i, email in enumerate(emails):
                resp = http.post(
                    "/api/v1/auth/register",
                    json={
                        "email": email,
                        "password": "Password123",
                        "full_name": f"Race {i}",
                    },
                )

                if resp.status_code != 201:
                    failures.append(f"register #{i}: HTTP {resp.status_code}")

                    continue

                token = resp.json()["access_token"]
                # IMMEDIATE follow-up on the same kept-alive connection
                follow = http.get(
                    "/api/v1/orgs", headers={"Authorization": f"Bearer {token}"}
                )

                if follow.status_code == 401:
                    unauthorized += 1
                elif follow.status_code != 200:
                    failures.append(f"follow-up #{i}: HTTP {follow.status_code}")
    finally:
        server.should_exit = True
        thread.join(timeout=5)

        with contextlib.suppress(Exception):
            await _cleanup(emails)

        with contextlib.suppress(Exception):
            from app.core.database import engine

            await engine.dispose()

    print(f"iterations:      {n}")
    print(f"401 after reg.:  {unauthorized}")

    if failures:
        print("other failures:")

        for f in failures:
            print(f"  - {f}")

    verdict = "RACE PRESENT" if unauthorized else "OK (no race)"
    print(f"result:          {verdict}")

    return 1 if unauthorized or failures else 0


if __name__ == "__main__":
    iterations = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    raise SystemExit(asyncio.run(main(iterations)))
