from datetime import datetime
from typing import Optional, Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .complaint import Complaint


class UserBase(BaseModel):
    username: str
    firstname: str
    lastname: str
    email: EmailStr
    school: str
    department: str


class UserCreate(UserBase):
    password: Annotated[
        str,
        Field(
            ...,
            description="Password of the user, must be at least 8 characters long, contain at least one digit, one uppercase letter, one lowercase letter, one special character and must not contain spaces",
        ),
    ]

    @field_validator("password")
    def password_validator(cls, value: str):
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char in "!@#$%^&*()-_+=" for char in value):
            raise ValueError("Password must contain at least one special character")
        if " " in value:
            raise ValueError("Password must not contain spaces")
        return value


class User(UserBase):
    model_config: ConfigDict = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool
    is_superuser: bool
    last_login: Optional[datetime]

    complaints: list[Complaint] = []


class PasswordUpdate(BaseModel):
    password: Annotated[
        str,
        Field(
            ...,
            description="Password of the user, must be at least 8 characters long, contain at least one digit, one uppercase letter, one lowercase letter, one special character and must not contain spaces",
        ),
    ]

    @field_validator("password")
    def password_validator(cls, value: str):
        if not any(char.isdigit() for char in value):
            raise ValueError("Password must contain at least one digit")
        if not any(char.isupper() for char in value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char in "!@#$%^&*()-_+=" for char in value):
            raise ValueError("Password must contain at least one special character")
        if " " in value:
            raise ValueError("Password must not contain spaces")
        return value
