from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings, oauth2_scheme
from ..crud.user import (
    get_user_by_email,
    get_user_by_username,
    create_user,
    update_user_password,
)
from ..crud.token import (
    create_access_token,
    create_refresh_token,
    get_token_by_jti,
    revoke_token,
    revoke_active_tokens,
)
from ..db.models import Token, User
from ..dependencies import get_async_session, authenticate, get_current_active_user
from ..forms.auth import SignUpForm
from ..schemas.token import Token as TokenSchema
from ..schemas.user import User as UserSchema, UserCreate, PasswordUpdate
from ..utils.security import get_password_hash, create_token, verify_payload


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=TokenSchema,
    summary="Login to get access token",
    status_code=status.HTTP_201_CREATED,
)
async def login_for_access_token(
    user: Annotated[User | None, Depends(authenticate)],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    # Generate access token
    access_token_expires_at: datetime = datetime.now() + timedelta(
        minutes=settings.access_token_expiry_minutes
    )
    username = await user.awaitable_attrs.username
    user_id = await user.awaitable_attrs.id
    access_token, access_jti = await create_token(
        data={"sub": username},
        expires_at=timedelta(minutes=settings.access_token_expiry_minutes),
    )
    # Save the token to the database
    await create_access_token(
        session=async_session,
        jti=access_jti,
        expires_at=access_token_expires_at,
        user_id=user_id,
    )

    # Generate refresh token
    refresh_token_expires_at: datetime = datetime.now() + timedelta(
        days=settings.refresh_token_expiry_days
    )
    refresh_token, refresh_jti = await create_token(
        data={"sub": username},
        expires_at=timedelta(days=settings.refresh_token_expiry_days),
    )
    # Save the token to the database
    await create_refresh_token(
        session=async_session,
        access_jti=access_jti,
        jti=refresh_jti,
        expires_at=refresh_token_expires_at,
        user_id=user_id,
    )

    return TokenSchema(
        access_token=access_token,
        access_token_expires_at=access_token_expires_at,
        refresh_token=refresh_token,
        refresh_token_expires_at=refresh_token_expires_at,
        token_type="bearer",
    )


@router.post(
    "/token/refresh",
    response_model=TokenSchema,
    summary="Refresh access token",
    status_code=status.HTTP_201_CREATED,
)
async def refresh_access_token(
    token: Annotated[str, Depends(oauth2_scheme)],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    # Verify the token
    username, jti = await verify_payload(token)
    token: Token | None = await get_token_by_jti(session=async_session, jti=jti)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if await token.awaitable_attrs.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the user
    user: User | None = await get_user_by_username(
        session=async_session, username=username
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Generate access token
    access_token_expires_at: datetime = datetime.now() + timedelta(
        minutes=settings.access_token_expiry_minutes
    )
    access_token, jti = await create_token(
        data={"sub": username},
        expires_at=timedelta(minutes=settings.access_token_expiry_minutes),
    )
    # Revoke the old token
    old_token_jti = await token.awaitable_attrs.access_jti
    old_token = await get_token_by_jti(session=async_session, jti=old_token_jti)
    await revoke_token(
        session=async_session, token=old_token, reason="Refresh token used"
    )
    user_id = user.awaitable_attrs.id
    # Save the token to the database
    await create_access_token(
        session=async_session,
        jti=jti,
        expires_at=access_token_expires_at,
        user_id=user_id,
    )

    return TokenSchema(
        access_token=access_token,
        access_token_expires_at=access_token_expires_at,
        token_type="bearer",
    )


@router.post(
    "/",
    response_model=UserSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Sign up user",
)
async def signup(
    form: Annotated[SignUpForm, Depends()],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    form: UserCreate = form.model()
    form_data = form.model_dump()

    # Check if user already exists
    if await get_user_by_email(session=async_session, email=form_data["email"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )
    if await get_user_by_username(
        session=async_session, username=form_data["username"]
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists",
        )

    # Hash the password
    password = form_data.pop("password")
    if password:
        form_data["hashed_password"] = get_password_hash(password=password)

    # Create the user
    user = User(**form_data)
    try:
        return await create_user(session=async_session, user=user)
    except IntegrityError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e.orig))


@router.post(
    "/logout",
    summary="Logout user",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout(
    token: Annotated[str, Depends(oauth2_scheme)],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    # Verify the token
    _, jti = await verify_payload(token)
    token: Token | None = await get_token_by_jti(session=async_session, jti=jti)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if await token.awaitable_attrs.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke the token
    await revoke_token(session=async_session, token=token, reason="User logged out")

    return None


@router.post(
    "/logout/all",
    summary="Logout user from all devices",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def logout_all(
    user: Annotated[User, Depends(get_current_active_user)],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    await revoke_active_tokens(
        session=async_session,
        user_id=await user.awaitable_attrs.id,
        reason="User logged out from all devices",
    )
    return None


@router.post(
    "/reset-password",
    summary="Reset password",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UserSchema,
)
async def reset_password(
    password: Annotated[str, Form(title="New password")],
    token: Annotated[str, Form(title="Reset token")],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    # Validate the password
    try:
        password = PasswordUpdate(password=password).password
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )
    # Verify the token
    username, jti = await verify_payload(token)
    token: Token | None = await get_token_by_jti(session=async_session, jti=jti)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if await token.awaitable_attrs.revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get the user
    user: User | None = await get_user_by_username(
        session=async_session, username=username
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await update_user_password(
        session=async_session,
        user=user,
        password=get_password_hash(password),
    )

    data = user.__dict__
    data["complaints"] = await user.awaitable_attrs.complaints
    return UserSchema(
        **data,
    )
