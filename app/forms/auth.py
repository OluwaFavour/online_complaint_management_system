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
        firstname: Annotated[str, Form(title="First Name")],
        lastname: Annotated[str, Form(title="Last Name")],
        email: Annotated[EmailStr, Form(title="Email")],
        password: Annotated[str, Form(title="Password")],
        school: Annotated[str, Form(title="School")],
        department: Annotated[str, Form(title="Department")],
    ):
        self.username = username
        self.firstname = firstname
        self.lastname = lastname
        self.email = email
        self.password = password
        self.school = school
        self.department = department

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
                username=self.username,
                email=self.email,
                password=self.password,
                firstname=self.firstname,
                lastname=self.lastname,
                school=self.school,
                department=self.department,
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
