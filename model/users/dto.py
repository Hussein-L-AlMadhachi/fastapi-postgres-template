from pydantic import BaseModel

class UserPasswordLogin(BaseModel):
    username: str
    password: str

class UserPhoneLogin(BaseModel):
    phone_number: str
    password: str

class UserEmailLogin(BaseModel):
    phone_number: str
    password: str

class UserSignup(BaseModel):
    phone_number: str
    password: str

class UserPasswordChange(BaseModel):
    phone_number: str
    password: str


class UserPhoneChange(BaseModel):
    phone_number: str
    password: str

class UserEmailChange(BaseModel):
    phone_number: str
    password: str

class User(BaseModel):
    id: int
    username: str
    phone_number: str
    email: str
    password: str

