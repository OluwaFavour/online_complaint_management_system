import datetime
from typing import Optional
from uuid import uuid4, UUID

from fastapi import UploadFile
from sqlalchemy import func, ForeignKey
from sqlalchemy.orm import mapped_column, relationship, Mapped

from ..enums import ComplaintStatus, TokenType
from .config import Base
from ..core.config import settings
from ..utils.cloudinary import upload_image
from ..utils.security import get_password_hash


class OTP(Base):
    """
    OTP model to store OTPs for email verification and password reset.

    Attributes:
        id (UUID): The primary key of the OTP.
        email (str): The email of the user the OTP belongs to.
        otp (str): The OTP code.
    """

    __tablename__ = "otps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(unique=True)
    otp: Mapped[str] = mapped_column()


class Token(Base):
    """
    Token model to store JWT tokens

    Attributes:
        id (UUID): The primary key of the token.
        user_id (UUID): The ID of the user the token belongs to (foreign key).
        jti (str): The unique identifier of the token.
        created_at (datetime): The timestamp when the token was created.
        expires_at (datetime): The timestamp when the token expires.
        revoked (bool): Whether the token has been revoked.
        revoked_at (Optional[datetime]): The timestamp when the token was revoked.
        reason (Optional[str]): The reason for revoking the token.
        type (TokenType): The type of the token (access or refresh).
        user (User): The user the token belongs to (relationship).

    Methods:
        revoke: Revoke the token.
    """

    __tablename__ = "tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    jti: Mapped[str] = mapped_column(unique=True)
    access_jti: Mapped[Optional[str]] = mapped_column(unique=True)
    created_at: Mapped[datetime.datetime] = mapped_column(insert_default=func.now())
    expires_at: Mapped[datetime.datetime] = mapped_column()
    revoked: Mapped[bool] = mapped_column(insert_default=False)
    revoked_at: Mapped[Optional[datetime.datetime]] = mapped_column()
    reason: Mapped[Optional[str]] = mapped_column()
    type: Mapped[TokenType]

    user: Mapped["User"] = relationship("User", back_populates="tokens")

    async def revoke(self, reason: Optional[str] = None) -> None:
        """
        Revoke the token.

        Args:
            reason (Optional[str]): The reason for revoking the token.
        """
        self.revoked = True
        self.revoked_at = datetime.datetime.now()
        self.reason = reason


class User(Base):
    """
    User model to store user information.

    Attributes:
        id (UUID): The primary key of the user.
        username (str): The unique username of the user.
        email (str): The unique email of the user.
        hashed_password (str): The hashed password of the user.
        is_email_verified (bool): Whether the user's email is verified.
        is_active (bool): Whether the user account is active.
        is_superuser (bool): Whether the user has superuser privileges.
        last_login (Optional[datetime]): The timestamp of the user's last login.
        created_at (datetime): The timestamp when the user was created.
        complaints (list[Complaint]): The list of complaints associated with the user (relationship).
        tokens (list[Token]): The list of tokens associated with the user (relationship).

    Methods:
        set_password: Set the user's password.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(insert_default=True)
    is_email_verified: Mapped[bool] = mapped_column(insert_default=False)
    is_superuser: Mapped[bool] = mapped_column(insert_default=False)
    last_login: Mapped[Optional[datetime.datetime]] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=func.now(),
    )

    complaints: Mapped[list["Complaint"]] = relationship(
        "Complaint",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    tokens: Mapped[list["Token"]] = relationship(
        "Token", back_populates="user", cascade="all, delete-orphan"
    )
    feedbacks: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="user", lazy="selectin"
    )

    async def set_password(self, password: str) -> None:
        """
        Set the user's password.

        Args:
            password (str): The new password for the user.
        """
        self.hashed_password = await get_password_hash(password)

    async def verify_email(self) -> None:
        """
        Verify the user's email.
        """
        self.is_email_verified = True


class Complaint(Base):
    """
    Complaint model to store user complaints.

    Attributes:
        id (UUID): The primary key of the complaint.
        user_id (UUID): The ID of the user who submitted the complaint (foreign key).
        type (str): The type of the complaint.
        description (str): The detailed description of the complaint.
        supporting_docs (Optional[str]): URL to the supporting documents for the complaint.
        created_at (datetime): The timestamp when the complaint was created.
        status (ComplaintStatus): The current status of the complaint.
        user (User): The user who submitted the complaint (relationship).

    Methods:
        update_status: Update the status of the complaint.
    """

    __tablename__ = "complaints"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column()
    description: Mapped[str] = mapped_column()
    supporting_docs: Mapped[Optional[str]] = mapped_column(
        nullable=True,
        comment="URL to cloudinary <user_id>/<complaint>/supporting_docs folder",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=func.now(),
    )
    status: Mapped[ComplaintStatus] = mapped_column(
        insert_default=ComplaintStatus.NEW,
    )

    user: Mapped["User"] = relationship("User", back_populates="complaints")
    feedbacks: Mapped[list["Feedback"]] = relationship(
        "Feedback", back_populates="complaint", lazy="selectin"
    )

    async def update_status(self, status: ComplaintStatus) -> None:
        """
        Update the status of the complaint.

        Args:
            status (ComplaintStatus): The new status of the complaint.
        """

        # First validate status transition
        if self.status == ComplaintStatus.NEW and status == ComplaintStatus.PENDING:
            self.status = status
        elif (
            self.status == ComplaintStatus.PENDING and status == ComplaintStatus.PAUSED
        ):
            self.status = status
        elif (
            self.status == ComplaintStatus.PAUSED and status == ComplaintStatus.PENDING
        ):
            self.status = status
        elif (
            self.status == ComplaintStatus.PENDING
            and status == ComplaintStatus.RESOLVED
        ):
            self.status = status
        else:
            raise ValueError(
                f"Invalid status transition, you can't move from {self.status} to {status}"
            )

    async def upload_supporting_docs(self, supporting_docs: list[UploadFile]) -> None:
        """
        Upload supporting documents for the complaint.

        Args:
            supporting_docs (list[UploadFile]): List of supporting documents to upload.
        """
        # Upload supporting documents to cloudinary
        folder = f"{settings.app_name}/{await self.awaitable_attrs.user_id}/{await self.awaitable_attrs.id}/supporting_docs"
        for doc in supporting_docs:
            url = await upload_image(asset_folder=folder, image=doc.file)
            print(url)
            if self.supporting_docs:
                self.supporting_docs += f" {url}"
            else:
                self.supporting_docs = url

    async def get_supporting_docs(self) -> list[str]:
        """
        Get the list of URLs for the supporting documents.

        Returns:
            list[str]: List of URLs for the supporting documents.
        """
        if self.supporting_docs:
            return self.supporting_docs.split(" ")
        return []


class Feedback(Base):
    """
    Feedback model to store user feedback.

    Attributes:
        id (UUID): The primary key of the feedback.
        message_id (str): The unique message ID of the feedback.
        user_id (UUID): The ID of the user who submitted the feedback (foreign key).
        complaint_id (UUID): The ID of the complaint the feedback is related to (foreign key).
        message (str): The feedback message.
        created_at (datetime): The timestamp when the feedback was created.
        user (User): The user who submitted the feedback (relationship).
    """

    __tablename__ = "feedbacks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[str] = mapped_column()
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    complaint_id: Mapped[UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE")
    )
    message: Mapped[str] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=func.now(),
    )

    user: Mapped["User"] = relationship("User", back_populates="feedbacks")
    complaint: Mapped["Complaint"] = relationship(
        "Complaint", back_populates="feedbacks"
    )
