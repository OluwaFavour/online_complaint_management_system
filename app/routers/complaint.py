from typing import Annotated, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Path,
    status,
    UploadFile,
    Query,
)
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_pagination import paginate, Params
from fastapi_pagination.links import Page

from ..crud.complaint import (
    create_complaint,
    delete_complaint,
    get_complaint_by_id,
    get_complaints_by_user_id,
)
from ..crud.feedback import create_feedback, get_feedback_by_id
from ..db.models import Complaint, User
from ..dependencies import get_current_active_user, get_async_session
from ..enums import ComplaintStatus
from ..forms.complaint import ComplaintCreateForm
from ..schemas.complaint import (
    Complaint as ComplaintSchema,
    ComplaintCountByStatus,
    ComplaintCountWithStatusAndTotal,
    Detail,
)
from ..schemas.feedback import Feedback as FeedbackSchema
from ..utils.feedback import reply_feedback


router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint",
    response_model=ComplaintSchema,
    responses={status.HTTP_400_BAD_REQUEST: {"model": Detail}},
)
async def add_complaint(
    form: Annotated[ComplaintCreateForm, Depends()],
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    complaint = None
    try:
        complaint = Complaint(
            type=form.type,
            description=form.description,
            user_id=user.id,
        )
        complaint = await create_complaint(session=session, complaint=complaint)
        supporting_docs: list[UploadFile] = form.supporting_docs
        if supporting_docs:
            await complaint.upload_supporting_docs(supporting_docs=supporting_docs)
            await session.commit()
            await session.refresh(complaint)
        return complaint
    except Exception as e:
        # Rollback the transaction if an error occurs
        if complaint:
            await delete_complaint(session=session, complaint=complaint)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(e)}
        )


@router.get(
    "/count",
    summary="Get complaint count classified by status and total count",
    response_model=ComplaintCountWithStatusAndTotal,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_400_BAD_REQUEST: {"model": Detail}},
)
async def get_complaint_count_with_status_and_total(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    try:
        new_complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, status_type=ComplaintStatus.NEW.name
        )
        pending_complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, status_type=ComplaintStatus.PENDING.name
        )
        paused_complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, status_type=ComplaintStatus.PAUSED.name
        )
        resolved_complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, status_type=ComplaintStatus.RESOLVED.name
        )
        new_count = len(new_complaints)
        pending_count = len(pending_complaints)
        paused_count = len(paused_complaints)
        resolved_count = len(resolved_complaints)
        total_count = new_count + pending_count + paused_count + resolved_count
        response = ComplaintCountWithStatusAndTotal(
            new=new_count,
            pending=pending_count,
            paused=paused_count,
            resolved=resolved_count,
            total=total_count,
        )
        return response
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(e)}
        )


@router.get(
    "/{complaint_id}",
    summary="Get a complaint by ID",
    response_model=ComplaintSchema,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": Detail},
        status.HTTP_403_FORBIDDEN: {"model": Detail},
    },
)
async def get_complaint(
    complaint_id: UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Complaint not found"},
        )
    if complaint.user_id != user.id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "You are not authorized to view this complaint"},
        )
    return complaint


@router.get(
    "/",
    summary="Get all complaints",
    response_model=Page[ComplaintSchema],
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_400_BAD_REQUEST: {"model": Detail}},
)
async def get_complaints(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
    type: Annotated[Optional[str], Query()] = None,
    status_type: Annotated[Optional[ComplaintStatus], Query()] = None,
    day: Annotated[Optional[int], Query(gt=0, le=31)] = None,
    month: Annotated[Optional[int], Query(gt=0, le=12)] = None,
    year: Annotated[Optional[str], Query(pattern=r"^\d{4}$", example="2024")] = None,
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
        complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, **filters
        )
        return paginate(complaints, params=Params(size=10))
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(e)}
        )


@router.get(
    "/count/{status_type}",
    summary="Get complaint count by status_type",
    response_model=ComplaintCountByStatus,
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_400_BAD_REQUEST: {"model": Detail}},
)
async def get_complaint_count_by_status(
    status_type: ComplaintStatus,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    try:
        complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, status_type=status_type.name
        )
        return ComplaintCountByStatus(status=status_type, count=len(complaints))
    except ValueError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(e)}
        )


@router.post(
    "/{complaint_id}/feedback/{feedback_id}",
    summary="Reply to a feedback",
    response_model=FeedbackSchema,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": Detail},
        status.HTTP_403_FORBIDDEN: {"model": Detail},
        status.HTTP_400_BAD_REQUEST: {"model": Detail},
    },
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
    user: Annotated[User, Depends(get_current_active_user)],
):
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Complaint not found"},
        )
    if complaint.user_id != user.id:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "You are not authorized to reply to this feedback"},
        )
    feedback = await get_feedback_by_id(session=session, feedback_id=feedback_id)
    if not feedback:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Feedback not found"},
        )
    if feedback.complaint_id != complaint_id:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Feedback does not belong to the complaint"},
        )
    feedback = await reply_feedback(message=message, feedback=feedback, sender=user)
    feedback = await create_feedback(session=session, feedback=feedback)
    return feedback
