from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.models import User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """
    Get a user by their email address

    Args:
        session (AsyncSession): The database session
        email (str): The email address of the user

    Returns:
        User | None: The user with the given email address, or None if not found
    """
    user = await session.execute(select(User).filter_by(email=email))
    return user.scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """
    Get a user by their username

    Args:
        session (AsyncSession): The database session
        username (str): The username of the user

    Returns:
        User | None: The user with the given username, or None if not found
    """
    user = await session.execute(select(User).filter_by(username=username))
    return user.scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """
    Get a user by their ID

    Args:
        session (AsyncSession): The database session
        user_id (UUID): The ID of the user

    Returns:
        User | None: The user with the given ID, or None if not found
    """
    user = await session.execute(select(User).filter_by(id=user_id))
    return user.scalar_one_or_none()


async def create_user(session: AsyncSession, user: User) -> User:
    """
    Create a new user

    Args:
        session (AsyncSession): The database session
        user (User): The user to create

    Returns:
        User: The created user
    """
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user(session: AsyncSession, user: User, **kwargs) -> User:
    """
    Update a user with the given values

    Args:
        session (AsyncSession): The database session
        user (User): The user to update
        **kwargs: The values to update

    Returns:
        User: The updated user

    Raises:
        ValueError: If any invalid keys are provided
    """
    possible_keys = {
        "email",
        "is_active",
        "is_superuser",
        "last_login",
    }
    if not (extra_keys := set(kwargs.keys()) - possible_keys):
        raise ValueError(f"Invalid keys: {extra_keys}")
    user = await session.execute(update(User).filter_by(id=user.id).values(**kwargs))
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_password(
    session: AsyncSession, user: User, password: str
) -> User:
    """
    Update a user's password

    Args:
        session (AsyncSession): The database session
        user (User): The user to update
        password (str): The new password

    Returns:
        User: The updated user
    """
    user.set_password(password)
    await session.commit()
    await session.refresh(user)
    return user
