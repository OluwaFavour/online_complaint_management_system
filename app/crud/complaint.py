from uuid import UUID

from sqlalchemy import update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.models import Complaint


async def get_complaint_by_id(
    session: AsyncSession, complaint_id: UUID
) -> Complaint | None:
    """
    Get a complaint by its ID

    Args:
        session (AsyncSession): The database session
        complaint_id (UUID): The ID of the complaint

    Returns:
        Complaint | None: The complaint with the given ID, or None if not found
    """
    complaint = await session.execute(select(Complaint).filter_by(id=complaint_id))
    return complaint.scalar_one_or_none()


async def get_complaints_by_user_id(
    session: AsyncSession, user_id: UUID
) -> list[Complaint]:
    """
    Get all complaints by a user

    Args:
        session (AsyncSession): The database session
        user_id (UUID): The ID of the user

    Returns:
        list[Complaint]: The complaints by the user
    """
    complaints = await session.execute(select(Complaint).filter_by(user_id=user_id))
    return complaints.scalars().all()


async def create_complaint(session: AsyncSession, complaint: Complaint) -> Complaint:
    """
    Create a new complaint

    Args:
        session (AsyncSession): The database session
        complaint (Complaint): The complaint to create

    Returns:
        Complaint: The created complaint
    """
    session.add(complaint)
    await session.commit()
    return complaint


async def update_complaint(
    session: AsyncSession, complaint: Complaint, **kwargs
) -> Complaint:
    """
    Update a complaint

    Args:
        session (AsyncSession): The database session
        complaint (Complaint): The complaint to update
        **kwargs: The values to update

    Returns:
        Complaint: The updated complaint

    Raises:
        ValueError: If any invalid keys are provided
    """
    possible_keys = {
        "type",
        "description",
        "supporting_docs",
        "status",
    }
    if not (extra_keys := set(kwargs.keys()) - possible_keys):
        raise ValueError(f"Invalid keys: {extra_keys}")
    complaint = await session.execute(
        update(Complaint)
        .filter_by(id=await complaint.awaitable_attrs.id)
        .values(**kwargs)
    )
    await session.commit()
    return complaint


async def delete_complaint(session: AsyncSession, complaint: Complaint) -> None:
    """
    Delete a complaint

    Args:
        session (AsyncSession): The database session
        complaint (Complaint): The complaint to delete

    Returns:
        None
    """
    await session.execute(
        delete(Complaint).filter_by(id=await complaint.awaitable_attrs.id)
    )
    await session.commit()
