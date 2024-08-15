from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..db.models import OTP


async def create_otp(session: AsyncSession, otp: str, email: str) -> OTP:
    """
    Create a new OTP

    Args:
        session (AsyncSession): The database session
        otp (str): The OTP to create
        email (str): The email of the user

    Returns:
        OTP: The created OTP
    """
    otp = OTP(otp=otp, email=email)
    session.add(otp)
    await session.commit()
    await session.refresh(otp)
    return otp


async def get_otp_by_email(session: AsyncSession, email: str) -> OTP:
    """
    Get the OTP by email

    Args:
        session (AsyncSession): The database session
        email (str): The email of the user

    Returns:
        OTP: The OTP
    """
    result = await session.execute(select(OTP).filter(OTP.email == email))
    return result.scalar_one_or_none()


async def delete_otp(session: AsyncSession, otp: OTP) -> None:
    """
    Delete the OTP

    Args:
        session (AsyncSession): The database session
        otp (OTP): The OTP to delete
    """
    await session.execute(delete(OTP).filter(OTP.id == otp.id))
    await session.commit()
