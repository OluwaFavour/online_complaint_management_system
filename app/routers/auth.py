from aiosmtplib import SMTP
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status, Form
import jwt
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings, oauth2_scheme
from ..crud.otp import create_otp, delete_otp, get_otp_by_email
from ..crud.token import (
    create_access_token,
    create_refresh_token,
    get_token_by_jti,
    revoke_token,
    revoke_active_tokens,
)
from ..crud.user import (
    get_user_by_email,
    get_user_by_username,
    create_user,
    update_user_password,
)
from ..db.models import Token, User
from ..dependencies import (
    get_async_session,
    authenticate,
    get_current_active_user,
    get_async_smtp,
)
from ..forms.auth import SignUpForm
from ..schemas.token import Token as TokenSchema
from ..schemas.user import User as UserSchema, UserCreate, PasswordUpdate
from ..utils.messages import get_html_from_template, send_email
from ..utils.security import (
    generate_otp,
    get_password_hash,
    create_token,
    verify_password,
    verify_payload,
)


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
    username = user.username
    user_id = user.id
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
    authorization: Annotated[str, Header(pattern="Bearer .*")],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    token = authorization.split(" ")[1]
    try:
        # Verify the token
        username, jti = await verify_payload(token)
        token: Token | None = await get_token_by_jti(session=async_session, jti=jti)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if token.revoked:
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
        old_token_jti = token.access_jti
        old_token = await get_token_by_jti(session=async_session, jti=old_token_jti)
        if not old_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token, refresh token not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        await revoke_token(
            session=async_session, token=old_token, reason="Refresh token used"
        )
        user_id = user.id
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
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials because of the following error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Sign up user",
    responses={
        400: {
            "description": "User with this email or username already exists",
            "content": {
                "application/json": {
                    "example": {"detail": "User with this email already exists"}
                }
            },
        },
        201: {
            "description": "OTP sent to your email",
            "content": {
                "application/json": {"example": {"message": "OTP sent to your email"}}
            },
        },
    },
)
async def signup(
    form: Annotated[SignUpForm, Depends()],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
    async_smtp: Annotated[SMTP, Depends(get_async_smtp)],
):
    form: UserCreate = await form.model()
    form_data = form.model_dump()

    # Check if user already exists
    if await get_user_by_email(session=async_session, email=form_data["email"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    # Hash the password
    password = form_data.pop("password")
    if password:
        form_data["hashed_password"] = await get_password_hash(password=password)

    # Create the user
    user = User(**form_data)
    try:
        user = await create_user(session=async_session, user=user)
        # Check if otp already exists for the email
        otp = await get_otp_by_email(session=async_session, email=form_data["email"])
        if otp:
            # Delete the existing OTP
            await delete_otp(session=async_session, otp=otp)
        otp = await generate_otp()

        # Encode the OTP
        encoded_otp = await get_password_hash(otp)

        # Store the encoded OTP in the database
        await create_otp(
            session=async_session, email=form_data["email"], otp=encoded_otp
        )
        # Send the reset token to the user
        plain_text = f"Your OTP is: {otp}"
        html_text = await get_html_from_template("email_otp_verification.html", otp=otp)
        await send_email(
            smtp=async_smtp,
            sender={"email": settings.from_email, "display_name": settings.from_name},
            recipient=form_data["email"],
            subject="Verify your email",
            plain_text=plain_text,
            html_text=html_text,
        )
        return {"message": "OTP sent to your email"}
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
    try:
        # Verify the token
        _, jti = await verify_payload(token)
        token: Token | None = await get_token_by_jti(session=async_session, jti=jti)
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if token.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Revoke the token
        await revoke_token(session=async_session, token=token, reason="User logged out")

        return None
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials because of the following error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


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
        user_id=user.id,
        reason="User logged out from all devices",
    )
    return None


@router.post(
    "/forgot-password",
    summary="Forgot password",
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        404: {
            "description": "User not found",
            "content": {"application/json": {"example": {"detail": "User not found"}}},
        },
        202: {
            "description": "Reset link sent to your email",
            "content": {
                "application/json": {
                    "example": {"message": "Reset link sent to your email"}
                }
            },
        },
    },
)
async def forgot_password(
    email: Annotated[EmailStr, Form(title="Email")],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
    async_smtp: Annotated[SMTP, Depends(get_async_smtp)],
):
    user: User | None = await get_user_by_email(session=async_session, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Generate reset token
    reset_token, _ = await create_token(
        data={"sub": user.username},
        expires_at=timedelta(minutes=settings.reset_token_expiry_minutes),
    )
    # Send the reset token to the user
    reset_link = f"{settings.frontend_url}/reset-password?token={reset_token}"
    plain_text = f"Click the link below to reset your password:\n{reset_link}"
    html_text = await get_html_from_template(
        template="reset_password.html",
        reset_link=reset_link,
        username=user.username,
        expiry_time=settings.reset_token_expiry_minutes,
    )
    await send_email(
        smtp=async_smtp,
        sender={"email": settings.from_email, "display_name": settings.from_name},
        recipient=email,
        subject="Reset your password",
        plain_text=plain_text,
        html_text=html_text,
    )
    return {"message": "Reset link sent to your email"}


@router.post(
    "/reset-password",
    summary="Reset password",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UserSchema,
    responses={
        400: {
            "description": "Invalid token",
            "content": {"application/json": {"example": {"detail": "Invalid token"}}},
        },
        401: {
            "description": "Invalid token",
            "content": {"application/json": {"example": {"detail": "Invalid token"}}},
        },
        422: {
            "description": "Invalid password",
            "content": {
                "application/json": {"example": {"detail": "Invalid password"}}
            },
        },
    },
)
async def reset_password(
    authorization: Annotated[str, Header(pattern="Bearer .*")],
    password: Annotated[str, Form(title="New password")],
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
    try:
        token = authorization.split(" ")[1]
        username, _ = await verify_payload(token)

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

        # Verify the new password
        if await verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password cannot be the same as the old password",
            )

        # Update the password
        await user.set_password(password)
        await async_session.commit()
        await async_session.refresh(user)
        return user
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials because of the following error: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/send-email-verification",
    summary="Send email verification",
    status_code=status.HTTP_200_OK,
    responses={
        404: {
            "description": "User not found",
            "content": {
                "application/json": {
                    "example": {"detail": "User not found, please sign up"}
                }
            },
        },
        400: {
            "description": "Email already verified",
            "content": {
                "application/json": {"example": {"detail": "Email already verified"}}
            },
        },
        200: {
            "description": "OTP sent to your email",
            "content": {
                "application/json": {"example": {"message": "OTP sent to your email"}}
            },
        },
    },
)
async def send_email_verification(
    email: Annotated[EmailStr, Form(title="Email")],
    async_smtp: Annotated[SMTP, Depends(get_async_smtp)],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    # Check if email is already verified
    user: User | None = await get_user_by_email(session=async_session, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found, please sign up",
        )
    elif user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    # Check if otp already exists for the email
    otp = await get_otp_by_email(session=async_session, email=email)
    if otp:
        # Delete the existing OTP
        await delete_otp(session=async_session, otp=otp)

    otp = await generate_otp()

    # Encode the OTP
    encoded_otp = await get_password_hash(otp)

    # Store the encoded OTP in the database
    await create_otp(session=async_session, email=email, otp=encoded_otp)
    # Send the reset token to the user
    plain_text = f"Your OTP is: {otp}"
    html_text = await get_html_from_template("email_otp_verification.html", otp=otp)
    await send_email(
        smtp=async_smtp,
        sender={"email": settings.from_email, "display_name": settings.from_name},
        recipient=email,
        subject="Verify your email",
        plain_text=plain_text,
        html_text=html_text,
    )
    return {"message": "OTP sent to your email"}


@router.post(
    "/verify-email",
    summary="Verify email",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=UserSchema,
)
async def verify_email(
    email: Annotated[EmailStr, Form(title="Email")],
    otp: Annotated[str, Form(title="OTP")],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    # Check if email is already verified
    user: User | None = await get_user_by_email(session=async_session, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found, please sign up",
        )
    elif user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already verified",
        )

    # Get the OTP
    otp_data = await get_otp_by_email(session=async_session, email=email)
    if not otp_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTP not found",
        )

    # Verify the OTP
    if not await verify_password(otp.upper(), otp_data.otp):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )
    # Update the user
    await user.verify_email()
    await async_session.commit()
    # Delete the OTP
    await delete_otp(session=async_session, otp=otp_data)

    return user


@router.post(
    "/change-password",
    summary="Change password",
    status_code=status.HTTP_200_OK,
    responses={
        422: {
            "description": "Invalid password",
            "content": {
                "application/json": {"example": {"detail": "Invalid password"}}
            },
        },
        200: {
            "description": "Password updated successfully",
            "content": {
                "application/json": {
                    "example": {"message": "Password updated successfully"}
                }
            },
        },
    },
)
async def change_password(
    user: Annotated[User, Depends(get_current_active_user)],
    new_password: Annotated[str, Form(title="New password")],
    old_password: Annotated[str, Form(title="Old password")],
    async_session: Annotated[AsyncSession, Depends(get_async_session)],
):
    # Validate the password
    try:
        new_password = PasswordUpdate(password=new_password).password
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        )

    # Verify the old password
    if not await verify_password(old_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect old password",
        )

    # Verify the new password
    if new_password == old_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password cannot be the same as the old password",
        )

    # Update the password
    await user.set_password(new_password)
    await async_session.commit()
    await async_session.refresh(user)

    return {"message": "Password updated successfully"}
