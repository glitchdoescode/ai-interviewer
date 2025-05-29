from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from bson import ObjectId

class UserRole(str, Enum):
    CANDIDATE = "candidate"
    INTERVIEWER = "interviewer"
    ADMIN = "admin"

class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    roles: List[UserRole] = Field(default_factory=lambda: [UserRole.CANDIDATE])
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: Optional[str] = None

class User(UserBase):
    id: Optional[str] = Field(default=None, alias="_id")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        json_encoders={ObjectId: str}
    )

class UserInDB(User):
    hashed_password: Optional[str] = None 