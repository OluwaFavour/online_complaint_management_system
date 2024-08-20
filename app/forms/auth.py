from typing import Annotated

from fastapi import Form
from pydantic import EmailStr

from ..schemas.user import UserCreate


class SignUpForm:
    """
    Base class for the SignUpForm object.

    Attributes:
        username (str): The username of the user.
        email (EmailStr): The email address of the user.
        password (str): The password

    Methods:
        model: Create a UserCreate object based on the SignUpForm data.
    """

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
        """
        Create a UserCreate object based on the SignUpForm data.
        Args:
            None
        Returns:
            UserCreate: The UserCreate object representing the user data.
        """
        try:
            return UserCreate(
                username=self.username, email=self.email, password=self.password
            )
        except Exception as e:
            raise e


class SignInForm:
    """
    Base class for the SignInForm object.

    Attributes:
        username (EmailStr): The email address of the user.
        password (str): The password of the user.
    """

    def __init__(
        self,
        username: Annotated[EmailStr, Form(title="Email")],
        password: Annotated[str, Form(title="Password")],
    ):
        self.username = username
        self.password = password
