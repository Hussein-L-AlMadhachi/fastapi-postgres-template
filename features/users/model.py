"""Request and response models for the users module."""

from datetime import datetime
from typing import Annotated, Literal, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator

IdentifierType = Literal["username", "email", "phone_number"]
OtpIdentifierType = Literal["email", "phone_number"]



Username = Annotated[
    str,
    Field(min_length=3, max_length=127, pattern=r"^[A-Za-z0-9_.-]+$"),
]
Email = Annotated[
    str,
    Field(max_length=511, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
]
PhoneNumber = Annotated[
    str,
    Field(max_length=31, pattern=r"^\+?[0-9]{7,31}$"),
]



def _count_arguments(*values: str | None) -> int:
    return sum(value is not None for value in values)

class _Identifiers(BaseModel):
    username: Username | None = None
    email: Email | None = None
    phone_number: PhoneNumber | None = None



class UserSignup(_Identifiers):
    password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def _require_identifier(self) -> Self:
        if _count_arguments(self.username, self.email, self.phone_number) == 0:
            raise ValueError("at least one of username, email or phone_number is required")
        return self



class PasswordLogin(_Identifiers):

    password: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def _require_one_identifier(self) -> Self:
        if _count_arguments(self.username, self.email, self.phone_number) != 1:
            raise ValueError("exactly one of username, email or phone_number is required")
        return self

    def identifier(self) -> tuple[IdentifierType, str]:
        if self.username is not None:
            return "username", self.username
        if self.email is not None:
            return "email", self.email
        assert self.phone_number is not None
        return "phone_number", self.phone_number



class OtpRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: Email | None = None
    phone_number: PhoneNumber | None = None

    @model_validator(mode="after")
    def _require_one_identifier(self) -> Self:
        if _count_arguments(self.email, self.phone_number) != 1:
            raise ValueError("exactly one of email or phone_number is required")
        return self

    def identifier(self) -> tuple[OtpIdentifierType, str]:
        if self.email is not None:
            return "email", self.email
        assert self.phone_number is not None
        return "phone_number", self.phone_number



class OtpLogin(OtpRequest):

    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_: int
    username: str | None
    phone_number: str | None
    email: str | None
    role: str
    created_at: datetime | None


class UserListItemOut(UserOut):
    isdisabled: bool
