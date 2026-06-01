"""Send an advance notice for a new Terms/Privacy version.

Usage:
    .venv/bin/python scripts/send_legal_update.py \
        --policy-version 2026-09-15 --effective-date 2026-09-15
"""

import argparse
import asyncio
from datetime import UTC, date, datetime, time, timedelta

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.features.legal.notifications import send_legal_update_notifications


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-version", required=True)
    parser.add_argument("--effective-date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--terms-url")
    parser.add_argument("--privacy-url")

    return parser


async def _run(args: argparse.Namespace) -> int:
    if not settings.smtp_host:
        raise RuntimeError("SMTP_HOST must be configured before sending legal emails")

    effective_date = date.fromisoformat(args.effective_date)
    effective_at = datetime.combine(effective_date, time.min, tzinfo=UTC)

    if effective_at < datetime.now(UTC) + timedelta(days=14):
        raise ValueError("The effective date must be at least 14 days from now")

    base_url = settings.FRONTEND_URL.rstrip("/")
    result = await send_legal_update_notifications(
        AsyncSessionLocal,
        policy_version=args.policy_version,
        effective_at=effective_at,
        terms_url=args.terms_url or f"{base_url}/terms",
        privacy_url=args.privacy_url or f"{base_url}/privacy",
    )
    print(
        f"Legal update notifications: sent={result.sent}, "
        f"skipped={result.skipped}, failed={result.failed}"
    )

    return 1 if result.failed else 0


def main() -> int:
    args = _parser().parse_args()

    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
