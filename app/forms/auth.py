from typing import Annotated

from fastapi import Form
from pydantic import EmailStr

from ..schemas.user import UserCreate


class SignUpForm:
    def __init__(
        self,
        username: Annotated[str, Form(title="Username")],
        email: Annotated[EmailStr, Form(title="Email")],
        password: Annotated[str, Form(title="Password")],
    ):
        self.username = username
        self.email = email
        self.password = password

    async def model(self) -> UserCreate:
        return UserCreate(
            username=self.username, email=self.email, password=self.password
        )


class SignInForm:
    def __init__(
        self,
        username: Annotated[EmailStr, Form(title="Email")],
        password: Annotated[str, Form(title="Password")],
    ):
        self.username = username
        self.password = password
