from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserInDBBase(UserBase):
    id: Optional[str] = Field(alias="_id", default=None) # For MongoDB _id
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # role will be added in Sprint 2

    class Config:
        populate_by_name = True # Allows using alias _id
        from_attributes = True # For orm_mode, useful if we ever use an ODM

# This model can be used when reading from DB
class User(UserInDBBase):
    pass

# This model can be used for returning user info without password
class UserPublic(UserBase):
    id: str = Field(alias="_id")
    created_at: datetime
    # role will be added in Sprint 2

    class Config:
        populate_by_name = True
        from_attributes = True
