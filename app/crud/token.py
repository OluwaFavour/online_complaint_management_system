from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy import update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..core.config import settings
from ..db.models import Token
from ..enums import TokenType
from .user import get_user_by_id
from ..utils.security import create_token as jwt_create_token


async def create_token(session: AsyncSession, token: Token) -> Token:
    """
    Create a new token

    Args:
        session (AsyncSession): The database session
        token (Token): The token to create

    Returns:
        Token: The created token
    """
    session.add(token)
    await session.commit()
    await session.refresh(token)
    return token


async def create_access_token(
    session: AsyncSession, jti: str, expires_at: datetime, user_id: UUID
) -> Token:
    """
    Create an access token for the user.

    Args:
        session (AsyncSession): The database session
        jti (str): The unique identifier of the token.
        expires_at (datetime): The timestamp when the token expires.
        user_id (UUID): The ID of the user the token belongs to.

    Returns:
        Token: The access token.
    """
    token = Token(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        type=TokenType.ACCESS,
    )
    return await create_token(session=session, token=token)


async def create_refresh_token(
    session: AsyncSession,
    jti: str,
    expires_at: datetime,
    user_id: UUID,
    access_jti: str,
) -> Token:
    """
    Create a refresh token for the user.

    Args:
        session (AsyncSession): The database session
        jti (str): The unique identifier of the token.
        expires_at (datetime): The timestamp when the token expires.
        user_id (UUID): The ID of the user the token belongs to.

    Returns:
        Token: The refresh token.
    """
    token = Token(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        access_jti=access_jti,
        type=TokenType.REFRESH,
    )
    return await create_token(session=session, token=token)


async def generate_token_pair(
    session: AsyncSession, username: str, user_id: int
) -> tuple[str, datetime, str, datetime]:
    """
    Generates a pair of access and refresh tokens for a user.
    Args:
        session (AsyncSession): The async session object.
        username (str): The username of the user.
        user_id (int): The ID of the user.
    Returns:
        tuple[str, datetime, str, datetime]: A tuple containing the access token, access token expiry datetime,
        refresh token, and refresh token expiry datetime.
    """
    access_token_expires_at = datetime.now() + timedelta(
        minutes=settings.access_token_expiry_minutes
    )
    refresh_token_expires_at = datetime.now() + timedelta(
        days=settings.refresh_token_expiry_days
    )

    access_token, access_jti = await jwt_create_token(
        data={"sub": username},
        expires_at=timedelta(minutes=settings.access_token_expiry_minutes),
    )
    refresh_token, refresh_jti = await jwt_create_token(
        data={"sub": username},
        expires_at=timedelta(days=settings.refresh_token_expiry_days),
    )

    await create_access_token(
        session=session,
        jti=access_jti,
        expires_at=access_token_expires_at,
        user_id=user_id,
    )
    await create_refresh_token(
        session=session,
        access_jti=access_jti,
        jti=refresh_jti,
        expires_at=refresh_token_expires_at,
        user_id=user_id,
    )

    return (
        access_token,
        access_token_expires_at,
        refresh_token,
        refresh_token_expires_at,
    )


async def get_token_by_jti(session: AsyncSession, jti: str) -> Token | None:
    """
    Get a token by its JTI

    Args:
        session (AsyncSession): The database session
        jti (str): The JTI of the token

    Returns:
        Token | None: The token with the given JTI, or None if not found
    """
    token = await session.execute(select(Token).filter_by(jti=jti))
    return token.scalar_one_or_none()


async def delete_token(session: AsyncSession, jti: str) -> None:
    """
    Delete a token

    Args:
        session (AsyncSession): The database session
        jt (str): The JTI of the token

    Returns:
        None
    """
    await session.execute(delete(Token).filter_by(jti=jti))
    await session.commit()


async def revoke_token(
    session: AsyncSession, token: Token, reason: str | None = None
) -> None:
    """
    Revoke a token

    Args:
        session (AsyncSession): The database session
        token (Token): The token to revoke
        reason (str): The reason for revoking the token

    Returns:
        None
    """
    await token.revoke(reason)
    await session.commit()
    await session.refresh(token)


async def revoke_active_tokens(
    session: AsyncSession, user_id: UUID, reason: str
) -> None:
    """
    Revoke all active tokens for a user

    Args:
        session (AsyncSession): The database session
        user_id (UUID): The ID of the user
        reason (str): The reason for revoking the tokens

    Returns:
        None

    Raises:
        ValueError: If the user with the given ID is not found
    """
    user = await get_user_by_id(session, user_id)
    if not user:
        raise ValueError(f"User with id {user_id} not found")
    await session.execute(
        update(Token)
        .filter_by(user_id=user_id, revoked=False)
        .values(revoked=True, reason=reason, revoked_at=datetime.now())
    )
    await session.commit()


async def delete_all_revoked_tokens(session: AsyncSession) -> None:
    """
    Delete all revoked tokens

    Args:
        session (AsyncSession): The database session

    Returns:
        None
    """
    await session.execute(delete(Token).filter_by(revoked=True))
    await session.commit()
