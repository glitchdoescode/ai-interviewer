from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from ai_interviewer.models.user_models import UserRole # Import UserRole for typing
import uuid # For default user ID

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True
    full_name: Optional[str] = None
    roles: List[UserRole] = [UserRole.CANDIDATE]

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None # Allow password to be updated optionally
    email: Optional[EmailStr] = None # Allow email to be updated
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    roles: Optional[List[UserRole]] = None

class UserResponse(UserBase):
    id: str # Assuming ID is a string (e.g., MongoDB ObjectId as str)
    # full_name: Optional[str] = None # Already in UserBase
    # roles: List[UserRole] # Already in UserBase
    # email: EmailStr # Already in UserBase
    # is_active: bool # Already in UserBase

    class Config:
        from_attributes = True # Replaces orm_mode

class UserInDBBase(UserBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())) # Changed from Optional[str] to default factory for ID
    hashed_password: Optional[str] = None # Make hashed_password optional for OAuth or if not set
    
    class Config:
        from_attributes = True

# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    email: EmailStr
    roles: List[UserRole]

class TokenData(BaseModel):
    user_id: Optional[str] = None # Changed from email to user_id to match token payload
    roles: Optional[List[str]] = None # Roles can also be in token data

# --- Password Reset Schemas ---
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

# --- User Roles Update Schema ---
class UserRolesUpdate(BaseModel):
    roles: List[UserRole]

# Removed UserLogin as it's not directly used by the current /token endpoint (which uses OAuth2PasswordRequestForm)
# class UserLogin(BaseModel):
#     username: EmailStr # Using email as username
#     password: str
