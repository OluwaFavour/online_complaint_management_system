from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Path, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_pagination import paginate, Params
from fastapi_pagination.links import Page

from ..crud.complaint import get_all_complaints, get_complaint_by_id
from ..crud.feedback import create_feedback, get_feedback_by_id
from ..db.models import User, Complaint
from ..dependencies import get_async_session, get_current_active_super_user
from ..enums import ComplaintStatus
from ..schemas.complaint import Complaint as ComplaintSchema
from ..schemas.feedback import Feedback as FeedbackSchema
from ..utils.feedback import reply_complaint, reply_feedback

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/complaints/",
    summary="Get all complaints",
    response_model=Page[ComplaintSchema],
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_active_super_user)],
)
async def get_complaints(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    type: Annotated[Optional[str], Query()] = None,
    status_type: Annotated[Optional[ComplaintStatus], Query()] = None,
    day: Annotated[Optional[int], Query(gt=0, le=31)] = None,
    month: Annotated[Optional[int], Query(gt=0, le=12)] = None,
    year: Annotated[Optional[str], Query(pattern=r"r^\d{4}$", example="2024")] = None,
):
    filters = {
        "type": type,
        "status": status_type.name if status_type else None,
        "day": day,
        "month": month,
        "year": int(year) if year else None,
    }
    filters = {k: v for k, v in filters.items() if v is not None}
    try:
        complaints = await get_all_complaints(session=session, **filters)
        return paginate(complaints, params=Params(size=10))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/complaints/{complaint_id}/status",
    summary="Update the status of a complaint",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_active_super_user)],
)
async def update_complaint_status(
    complaint_id: UUID,
    status_type: ComplaintStatus,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    """
    Update the status of a complaint.
    The possible status transitions are:
        NEW -> PENDING
        PENDING -> PAUSED
        PAUSED -> PENDING
        PENDING -> RSOLVED

    Args:
        complaint_id (UUID): The ID of the complaint to update.
        status_type (ComplaintStatus): The new status of the complaint.
        session (AsyncSession): The database session.

    Returns:
        The updated complaint.

    Raises:
        HTTPException: If the complaint is not found or if there is a value error.
    """
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found"
        )
    try:
        await complaint.update_status(status=status_type)
        await session.commit()
        return complaint
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/complaints/{complaint_id}",
    summary="Reply to a complaint",
    response_model=FeedbackSchema,
    status_code=status.HTTP_200_OK,
)
async def reply_to_complaint(
    complaint_id: Annotated[UUID, Path(title="Complaint ID")],
    message: Annotated[str, Form(title="Message")],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_super_user)],
):
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found"
        )

    # reply to the complaint and create a feedback
    feedback = await reply_complaint(message=message, complaint=complaint, sender=user)
    feedback = await create_feedback(session=session, feedback=feedback)
    return feedback


@router.post(
    "/complaints/{complaint_id}/feedback/{feedback_id}",
    summary="Reply to a feedback",
    response_model=FeedbackSchema,
    status_code=status.HTTP_200_OK,
)
async def reply_to_feedback(
    complaint_id: Annotated[
        UUID,
        Path(
            title="Complaint ID",
            description="The ID of the complaint the feedback belongs to",
        ),
    ],
    feedback_id: Annotated[
        UUID,
        Path(title="Feedback ID", description="The ID of the feedback to reply to"),
    ],
    message: Annotated[str, Form(title="Message", description="The reply message")],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_super_user)],
):
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found"
        )
    feedback = await get_feedback_by_id(session=session, feedback_id=feedback_id)
    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found"
        )
    if await feedback.awaitable_attrs.complaint_id != complaint_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback does not belong to the complaint",
        )
    feedback = await reply_feedback(message=message, feedback=feedback, sender=user)
    feedback = await create_feedback(session=session, feedback=feedback)
    return feedback
