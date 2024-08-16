from datetime import datetime, timedelta
import secrets
from typing import Any
from uuid import uuid4

import jwt

from ..core.config import pwd_context, settings


async def generate_otp() -> str:
    """
    Generates a random OTP (One-Time Password) consisting of 6 alphanumeric characters.

    Returns:
        str: The generated OTP.
    """
    return "".join(
        secrets.choice("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ") for _ in range(6)
    )


async def get_password_hash(password) -> str:
    """
    Get the hashed password of the given password

    Args:
        password ([type]): The password to hash

    Returns:
        str: The hashed password
    """
    return pwd_context.hash(password)


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify the given password against the hashed password

    Args:
        plain_password (str): The password to verify
        hashed_password (str): The hashed password to verify against

    Returns:
        bool: True if the password is correct, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


async def create_token(
    data: dict[str, Any], expires_at: timedelta | None = None
) -> tuple[str, str]:
    """
    Create a token with the given data and expiration time

    Args:
        data (dict[str, Any]): The data to encode in the token
        expires_at (timedelta | None, optional): The expiration time of the token. Defaults to None.

    Returns:
        tuple[str, str]: The encoded token and jti
    """
    to_encode = data.copy()
    jti = str(uuid4())
    if expires_at:
        expire = datetime.now() + expires_at
    else:
        expire = datetime.now() + timedelta(
            minutes=settings.access_token_expiry_minutes
        )
    to_encode.update({"exp": expire, "jti": jti})
    encoded_jwt: str = jwt.encode(
        payload=to_encode, key=settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
    return encoded_jwt, jti


async def verify_payload(token: str) -> tuple[str, str]:
    """
    Verify the payload of the token and return the username and jti

    Args:
        token (str): The token to verify

    Returns:
        tuple[str, str]: The username and jti of the token

    Raises:
        jwt.ExpiredSignatureError: If the token has expired
        jwt.InvalidTokenError: If the token is invalid
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            jwt=token, key=settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        jti: str | None = payload.get("jti")
        username: str | None = payload.get("sub")
        if username is None or jti is None:
            raise jwt.InvalidTokenError()
        return username, jti
    except jwt.ExpiredSignatureError:
        raise jwt.ExpiredSignatureError("Token has expired")
    except jwt.InvalidTokenError:
        raise jwt.InvalidTokenError("Token is invalid")
