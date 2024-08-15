from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.models import Complaint, Feedback, User


async def create_feedback(session: AsyncSession, feedback: Feedback) -> Feedback:
    """
    Create a new feedback

    Args:
        session (AsyncSession): The database session
        feedback (Feedback): The feedback to create

    Returns:
        Feedback: The created feedback
    """
    session.add(feedback)
    await session.commit()
    return feedback


async def get_feedback_by_id(session: AsyncSession, feedback_id: UUID) -> Feedback:
    """
    Get a feedback by its ID

    Args:
        session (AsyncSession): The database session
        feedback_id (UUID): The ID of the feedback

    Returns:
        Feedback: The feedback with the given ID
    """
    feedback = await session.get(Feedback, feedback_id)
    return feedback


async def get_feedbacks(session: AsyncSession) -> list[Feedback]:
    """
    Get all feedbacks

    Args:
        session (AsyncSession): The database session

    Returns:
        list[Feedback]: List of all feedbacks
    """
    stmt = select(Feedback)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_feedbacks_by_user_id(
    session: AsyncSession, user_id: UUID
) -> list[Feedback]:
    """
    Get all feedbacks by a user

    Args:
        session (AsyncSession): The database session
        user_id (UUID): The ID of the user

    Returns:
        list[Feedback]: List of all feedbacks by the user
    """
    stmt = select(Feedback).where(Feedback.user_id == user_id)
    result = await session.execute(stmt)
    return result.scalars().all()


async def get_feedbacks_by_complaint_id(
    session: AsyncSession, complaint_id: UUID
) -> list[Feedback]:
    """
    Get all feedbacks by a complaint

    Args:
        session (AsyncSession): The database session
        complaint_id (UUID): The ID of the complaint

    Returns:
        list[Feedback]: List of all feedbacks by the complaint
    """
    stmt = select(Feedback).where(Feedback.complaint_id == complaint_id)
    result = await session.execute(stmt)
    return result.scalars().all()
