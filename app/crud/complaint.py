from uuid import UUID

from sqlalchemy import update, delete, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..core.config import settings
from ..db.models import Complaint
from ..enums import ComplaintStatus
from ..utils.cloudinary import delete_folder_by_prefix


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


async def get_all_complaints(
    session: AsyncSession,
    **filters,
) -> list[Complaint]:
    """
    Get all complaints

    Args:
        session (AsyncSession): The database session
        filters: The filters to apply

    Returns:
        list[Complaint]: The complaints
    """
    possible_filters = {"status_type", "type", "day", "month", "year"}
    invalid_filters = set(filters.keys()) - possible_filters
    if invalid_filters:
        raise ValueError(f"Invalid filters: {invalid_filters}")

    query = select(Complaint)

    for filter_key, value in filters.items():
        if filter_key == "day":
            query = query.where(extract("day", Complaint.created_at) == value)
        elif filter_key == "month":
            query = query.where(extract("month", Complaint.created_at) == value)
        elif filter_key == "year":
            query = query.where(extract("year", Complaint.created_at) == value)
        elif filter_key == "status_type":
            if value not in ComplaintStatus.__members__:
                raise ValueError(f"Invalid status: {value}")
            query = query.where(Complaint.status == ComplaintStatus[value])
        elif filter_key == "type":
            query = query.where(Complaint.type.ilike(f"%{value}%"))

    result = await session.execute(query)
    complaints = result.scalars().all()
    return complaints


async def get_complaints_by_user_id(
    session: AsyncSession,
    user_id: UUID,
    **filters,
) -> list[Complaint]:
    """
    Get all complaints by a user

    Args:
        session (AsyncSession): The database session
        user_id (UUID): The ID of the user
        filters: The filters to apply

    Returns:
        list[Complaint]: The complaints by the user
    """
    possible_filters = {"status_type", "type", "day", "month", "year"}
    invalid_filters = set(filters.keys()) - possible_filters
    if invalid_filters:
        raise ValueError(f"Invalid filters: {invalid_filters}")

    query = select(Complaint).where(Complaint.user_id == user_id)

    for filter_key, value in filters.items():
        if filter_key == "day":
            query = query.where(extract("day", Complaint.created_at) == value)
        elif filter_key == "month":
            query = query.where(extract("month", Complaint.created_at) == value)
        elif filter_key == "year":
            query = query.where(extract("year", Complaint.created_at) == value)
        elif filter_key == "status_type":
            if value not in ComplaintStatus.__members__:
                raise ValueError(f"Invalid status: {value}")
            query = query.where(Complaint.status == ComplaintStatus[value])
        elif filter_key == "type":
            query = query.where(Complaint.type.ilike(f"%{value}%"))

    result = await session.execute(query)
    complaints = result.scalars().all()
    return complaints


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
    folder = f"{settings.app_name}/{complaint.user_id}/{complaint.id}/supporting_docs"
    await delete_folder_by_prefix(folder)
    await session.commit()
