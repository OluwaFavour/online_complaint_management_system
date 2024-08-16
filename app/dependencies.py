import aiosmtplib
import jwt
from typing import AsyncGenerator, Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .core.config import oauth2_scheme, settings
from .crud.token import revoke_token, get_token_by_jti
from .crud.user import get_user_by_username, get_user_by_email
from .db.config import AsyncSessionLocal
from .db.models import Token, User
from .forms.auth import SignInForm
from .utils.security import verify_payload, verify_password


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Asynchronous generator function that returns an async session.

    Returns:
        AsyncGenerator[AsyncSession, None]: An asynchronous generator that yields an async session.

    Raises:
        None

    Example usage:
        ```
        async for session in get_async_session():
            # Use the session for database operations
            ...
        ```
    """
    db = AsyncSessionLocal()
    try:
        yield db
    finally:
        await db.close()


async def get_async_smtp():
    """
    Manage the SMTP connection by creating a new connection for each request.

    Raises:
        HTTPException: If there is an error connecting to the SMTP server, starting TLS, authenticating, or if any other SMTP exception occurs.

    Returns:
        async_smtp: An SMTP connection object.

    Example usage:
        ```
        async with get_async_smtp() as smtp:
            # Use the smtp connection for sending emails
        ```
    """
    async_smtp = aiosmtplib.SMTP(
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        use_tls=False,
        start_tls=False,
    )
    try:
        await async_smtp.connect()
        await async_smtp.starttls()
        await async_smtp.login(settings.smtp_login, settings.smtp_password)
        yield async_smtp
    except aiosmtplib.SMTPConnectError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Could not connect to SMTP server", "error": str(e)},
        )
    except aiosmtplib.SMTPHeloError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Could not start TLS", "error": str(e)},
        )
    except aiosmtplib.SMTPAuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Could not authenticate", "error": str(e)},
        )
    except aiosmtplib.SMTPException as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "An error occurred", "error": str(e)},
        )
    finally:
        try:
            await async_smtp.quit()
        except Exception as e:
            # Handle or log the exception if quitting fails
            print(f"Failed to quit SMTP connection cleanly: {e}")


async def authenticate(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    form_data: Annotated[SignInForm, Depends()],
) -> User | None:
    """
    Authenticate a user with the given email and password.

    Args:
        session (AsyncSession): The database session.
        email (str): The email of the user.
        password (str): The password of the user.

    Returns:
        User | None: The authenticated user, or None if not found.
    """
    email = form_data.username
    password = form_data.password
    user = await get_user_by_email(session=session, email=email)
    if not user:
        return None
    if not await verify_password(
        plain_password=password, hashed_password=user.hashed_password
    ):
        return None
    return user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> User:
    """
    Retrieves the current user based on the provided token.

    Args:
        token (str): The authentication token.
        async_session (AsyncSession): The asynchronous session.

    Returns:
        User: The current user.

    Raises:
        HTTPException: If the token is invalid, revoked, or the user is not found.
    """
    try:
        username, jti = await verify_payload(token)
        token: Token | None = await get_token_by_jti(session=async_session, jti=jti)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if token.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )
        user: User | None = await get_user_by_username(
            session=async_session, username=username
        )
        if not user:
            revoke_token(
                session=async_session,
                token=token,
                reason="User not found, token might be compromised",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found, token invalid",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_email_verified:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email not verified",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials because of the following error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the current active user.

    Parameters:
        current_user (User): The current user.

    Returns:
        User: The current active user.

    Raises:
        HTTPException: If the current user is inactive.

    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    return current_user


async def get_current_active_super_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    """
    Get the current active super user.

    Args:
        current_user (User): The current user.

    Returns:
        User: The current active super user.

    Raises:
        HTTPException: If the current user is inactive or not a superuser.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is not a superuser"
        )
    return current_user
