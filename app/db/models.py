import datetime
from typing import Optional
from uuid import uuid4, UUID

from sqlalchemy import func, ForeignKey
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import mapped_column, relationship, Mapped

from ..enums import ComplaintStatus, TokenType
from .config import Base
from ..utils.security import get_password_hash, verify_password


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
    username: Mapped[str] = mapped_column(unique=True, index=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column()
    is_active: Mapped[bool] = mapped_column(insert_default=True)
    is_superuser: Mapped[bool] = mapped_column(insert_default=False)
    last_login: Mapped[Optional[datetime.datetime]] = mapped_column()
    created_at: Mapped[datetime.datetime] = mapped_column(
        insert_default=func.now(),
    )

    complaints: Mapped[list["Complaint"]] = relationship(
        "Complaint", back_populates="user", cascade="all, delete-orphan"
    )
    tokens: Mapped[list["Token"]] = relationship(
        "Token", back_populates="user", cascade="all, delete-orphan"
    )

    async def set_password(self, password: str) -> None:
        """
        Set the user's password.

        Args:
            password (str): The new password for the user.
        """
        self.hashed_password = get_password_hash(password)


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

    user = relationship("User", back_populates="complaints")

    async def update_status(self, status: ComplaintStatus) -> None:
        """
        Update the status of the complaint.

        Args:
            status (ComplaintStatus): The new status of the complaint.
        """
        self.status = status
