from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_pagination import paginate, Params
from fastapi_pagination.links import Page

from ..crud.complaint import get_all_complaints, get_complaint_by_id
from ..db.models import User, Complaint
from ..dependencies import get_async_session, get_current_active_super_user
from ..enums import ComplaintStatus
from ..schemas.complaint import Complaint as ComplaintSchema

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/",
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
        response = [
            await ComplaintSchema.model_validate(complaint) for complaint in complaints
        ]
        return paginate(response, params=Params(size=10))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/{complaint_id}/status",
    summary="Update the status of a complaint",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_active_super_user)],
)
async def update_complaint_status(
    complaint_id: UUID,
    status_type: ComplaintStatus,
    session: Annotated[AsyncSession, Depends(get_async_session)],
):
    complaint = await get_complaint_by_id(session=session, complaint_id=complaint_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Complaint not found"
        )
    await complaint.update_status(status=status_type)
    await session.commit()
    return await ComplaintSchema.model_validate(complaint)
