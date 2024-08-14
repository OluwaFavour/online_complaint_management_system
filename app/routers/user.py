from typing import Annotated

from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..dependencies import get_async_session, get_current_active_user
from ..db.models import User
from ..schemas.user import User as UserSchema

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserSchema,
    summary="Get the current user",
)
async def get_current_user(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserSchema:
    return current_user
