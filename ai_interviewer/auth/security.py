from datetime import datetime, timedelta, timezone
from typing import Optional, Union, Any, Dict, List
# from passlib.context import CryptContext # No longer needed here
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from pydantic import EmailStr, ValidationError
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

from .config import settings
from . import models, schemas, services # Added services import
from ai_interviewer.auth import services as auth_services
from ai_interviewer.models.user_models import User, UserRole # User for return type
from .password_utils import verify_password, get_password_hash # IMPORT FROM NEW FILE

# 1. Password Hashing Context
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto") # MOVED

# 2. OAuth2PasswordBearer Scheme
# It uses the path to the token endpoint (e.g., /api/v1/auth/token)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token", auto_error=False)

# Custom dependency to get token from cookie or header
async def get_token_from_cookie_or_header(request: Request, token_from_header: Optional[str] = Depends(oauth2_scheme)) -> Optional[str]:
    token_from_cookie = request.cookies.get("access_token")
    logger.info(f"get_token_from_cookie_or_header: Token from cookie ('access_token'): {'SET' if token_from_cookie else 'NOT SET'}")

    if token_from_cookie:
        # Cookie value might be 'Bearer <token>', strip 'Bearer ' if present
        if token_from_cookie.lower().startswith("bearer "):
            logger.info("get_token_from_cookie_or_header: Returning token from cookie (stripped Bearer).")
            return token_from_cookie[7:]
        logger.info("get_token_from_cookie_or_header: Returning token from cookie (as is).")
        return token_from_cookie
    
    logger.info(f"get_token_from_cookie_or_header: Token from header (via OAuth2PasswordBearer): {'SET' if token_from_header else 'NOT SET'}")
    if token_from_header:
        logger.info("get_token_from_cookie_or_header: Returning token from header.")
        return token_from_header
    
    logger.warning("get_token_from_cookie_or_header: No token found in cookie or header, returning None.")
    return None

# 3. Password Utilities
# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return pwd_context.verify(plain_password, hashed_password) # MOVED
# 
# def get_password_hash(password: str) -> str:
#     return pwd_context.hash(password) # MOVED

# 4. JWT Utilities
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc), "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.REFRESH_SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[Dict[str, Any]]: # Return type more specific
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Optionally, validate token type if it's included in access tokens too
        # if payload.get("type") == "refresh": 
        #     logger.warning("Attempted to use refresh token as access token.") # Added logging
        #     return None 
        logger.info("Access token decoded successfully.") # Added logging
        return payload
    except jwt.ExpiredSignatureError: # Specific exception for expired token
        logger.warning("Access token has expired.")
        return None
    except JWTError as e: # Catch other JWT errors
        logger.warning(f"Invalid access token: {e}")
        return None
    except (ValidationError) as e: # Catch Pydantic validation errors if payload structure is wrong
        logger.warning(f"Access token payload validation error: {e}")
        return None

def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            logger.warning("Invalid token type provided to decode_refresh_token.")
            return None
        return payload
    except (JWTError, ValidationError) as e:
        logger.error(f"Refresh token decoding error: {e}")
        return None

# 5. Dependency to get current user
async def get_current_user(request: Request, token: Optional[str] = Depends(get_token_from_cookie_or_header)) -> User:
    # Local import to break circular dependency if server.py imports this module early
    from ai_interviewer.core.database import get_motor_db
    
    # Obtain db instance using the dependency
    # Note: We pass get_motor_db directly to Depends, FastAPI handles calling it.
    # So, we need to make db an argument of get_current_user that Depends injects.
    # This requires get_motor_db to be available for Depends at the time of definition.
    # The previous local import of get_motor_db inside the function was for when we called it directly.
    # For Depends(), the structure is slightly different if get_motor_db isn't available at parse time.

    # Corrected approach: db dependency should be passed to get_current_user
    # This means get_motor_db must be resolvable when security.py is parsed, 
    # if it's used as Depends(get_motor_db) in the signature. 
    # Given the circular import issues, it's safer to get db via a service call
    # or by making the db available through a contextvar or app state if possible.
    # Let's stick to the local import and direct call for now to ensure no top-level server import.

    db: AsyncIOMotorDatabase = await get_motor_db(request) # Call the imported function, passing the request

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    logger.info(f"get_current_user: Token received from get_token_from_cookie_or_header: {'PRESENT' if token else 'NONE'}")
    if token is None:
        logger.warning("get_current_user: Token is None, raising credentials_exception.")
        raise credentials_exception
    
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    user_id: Optional[str] = payload.get("user_id") # We stored 'user_id' in the token
    if user_id is None:
        # Could also check for 'sub' if that's preferred, but user_id is more direct
        raise credentials_exception
    
    user = await auth_services.get_user_by_id_service(user_id=user_id, db=db)
    if user is None:
        raise credentials_exception
    return user

# 6. Dependency to get current active user
async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# 7. Dependency for Role-Based Access Control
class RoleChecker:
    """
    Dependency that checks if the current user has at least one of the required roles.

    Usage:
        @app.get("/some-admin-route", dependencies=[Depends(RoleChecker([UserRole.ADMIN]))])
        async def get_admin_data(current_user: User = Depends(get_current_active_user)):
            # ... logic for admin users ...
            return {"message": "Admin data"}
    """
    def __init__(self, required_roles: List[UserRole]):
        self.required_roles = required_roles

    async def __call__(self, current_user: User = Depends(get_current_active_user)) -> None:
        if not self.required_roles: # If no roles are required, allow access
            return

        # Check if the user has any of the required roles
        has_required_role = any(user_role in self.required_roles for user_role in current_user.roles)
        
        if not has_required_role:
            # Construct a more informative error message
            required_roles_str = ", ".join(sorted([role.value for role in self.required_roles]))
            user_roles_str = ", ".join(sorted([role.value for role in current_user.roles]))
            
            logger.warning(
                f"Role access denied for user {current_user.email} (ID: {current_user.id}). "
                f"Required roles: [{required_roles_str}], User roles: [{user_roles_str}]."
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User does not have the required role(s): {required_roles_str}"
            )
        # Optional: Log successful role access if needed for auditing
        # logger.info(f"User {current_user.email} granted access based on roles: {user_roles_str}")

# Need to import List from typing and UserRole if not already at the top
# from typing import List (already there)
# from ai_interviewer.models.user_models import UserRole (already there)
# Add logger if not already defined (it is not defined in security.py)
logger = logging.getLogger(__name__)

# Keep existing password and JWT utilities if they were not moved to a separate security_utils.py
# from passlib.context import CryptContext
# from datetime import datetime, timedelta, timezone
# from typing import Optional
# from jose import jwt

# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES are defined in config.py or directly here

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return pwd_context.verify(plain_password, hashed_password)

# def get_password_hash(password: str) -> str:
#     return pwd_context.hash(password)

# def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
#     to_encode = data.copy()
#     if expires_delta:
#         expire = datetime.now(timezone.utc) + expires_delta
#     else:
#         expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
#     encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
#     return encoded_jwt

# def decode_access_token(token: str) -> Optional[dict]:
#     try:
#         payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
#         return payload
#     except (JWTError, ValidationError):
#         return None

