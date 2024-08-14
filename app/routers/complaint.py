from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_pagination import paginate, Params
from fastapi_pagination.links import Page

from ..crud.complaint import (
    create_complaint,
    delete_complaint,
    get_complaint_by_id,
    get_complaints_by_user_id,
)
from ..db.models import Complaint, User
from ..dependencies import get_current_active_user, get_async_session
from ..enums import ComplaintStatus
from ..forms.complaint import ComplaintCreateForm
from ..schemas.complaint import Complaint as ComplaintSchema, ComplaintCountByStatus


router = APIRouter(prefix="/api/complaints", tags=["complaints"])


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint",
    response_model=ComplaintSchema,
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
            user_id=await user.awaitable_attrs.id,
        )
        complaint = await create_complaint(session=session, complaint=complaint)
        supporting_docs: list[UploadFile] = form.supporting_docs
        if supporting_docs:
            await complaint.upload_supporting_docs(supporting_docs=supporting_docs)
            await session.commit()
        response = await ComplaintSchema.model_validate(complaint)
        return response
    except Exception as e:
        # Rollback the transaction if an error occurs
        if complaint:
            await delete_complaint(session=session, complaint=complaint)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/{complaint_id}",
    summary="Get a complaint by ID",
    response_model=ComplaintSchema,
    status_code=status.HTTP_200_OK,
)
async def get_complaint(
    complaint_id: UUID,
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
):
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found"
        )
    if complaint.awaitable_attrs.user_id != user.awaitable_attrs.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to view this complaint",
        )
    response = await ComplaintSchema.model_validate(complaint)
    return response


@router.get(
    "/",
    summary="Get all complaints",
    response_model=Page[ComplaintSchema],
    status_code=status.HTTP_200_OK,
)
async def get_complaints(
    session: Annotated[AsyncSession, Depends(get_async_session)],
    user: Annotated[User, Depends(get_current_active_user)],
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
        complaints = await get_complaints_by_user_id(
            session=session, user_id=user.id, **filters
        )
        response = [
            await ComplaintSchema.model_validate(complaint) for complaint in complaints
        ]
        return paginate(response, params=Params(size=10))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/count/{status_type}",
    summary="Get complaint count by status_type",
    response_model=ComplaintCountByStatus,
    status_code=status.HTTP_200_OK,
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
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
