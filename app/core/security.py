import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from uuid_extensions import uuid7

from app.core.config import settings


def create_access_token(subject: str) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        # Keep fractional precision: get_current_user compares iat against the
        # DB timestamp of the last password change; truncating to whole seconds
        # makes fresh access tokens look older than the user row (false 401s).
        "iat": now.timestamp(),
        "type": "access",
    }
    secret = settings.secret_key.get_secret_value()

    return jwt.encode(to_encode, secret, algorithm="HS256")


def create_refresh_token(subject: str, sid: str | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)

    if sid is None:
        sid = str(uuid7())

    to_encode = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "type": "refresh",
        "sid": str(sid),
    }
    secret = settings.secret_key.get_secret_value()

    return jwt.encode(to_encode, secret, algorithm="HS256")


def create_reset_token(subject: str) -> str:
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.reset_token_expire_minutes)

    to_encode = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        # One-time use check: reset_password compares iat against
        # user.updated_at, so a token issued before the last password change
        # is rejected. Fractional precision avoids the same false-positive
        # problem described for access tokens.
        "iat": now.timestamp(),
        "type": "reset",
    }
    secret = settings.secret_key.get_secret_value()

    return jwt.encode(to_encode, secret, algorithm="HS256")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def decode_token(token: str, expected_type: str | None = None) -> dict | None:
    try:
        secret = settings.secret_key.get_secret_value()
        payload = jwt.decode(token, secret, algorithms=["HS256"])

        if expected_type is not None and payload.get("type") != expected_type:
            return None

        return payload
    except jwt.PyJWTError:
        return None


def decode_access_token(token: str) -> dict | None:
    return decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> dict | None:
    return decode_token(token, expected_type="refresh")


def decode_reset_token(token: str) -> dict | None:
    return decode_token(token, expected_type="reset")


# === BCRYPT HASHING ===


def get_password_hash(password: str) -> str:
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()

    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        plain_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")

        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        return False


async def get_password_hash_async(password: str) -> str:
    return await asyncio.to_thread(get_password_hash, password)


async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await asyncio.to_thread(verify_password, plain_password, hashed_password)
