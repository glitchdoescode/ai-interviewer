from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from motor.motor_asyncio import AsyncIOMotorDatabase

# Imports from our auth module
from ai_interviewer.auth import services as auth_services
from ai_interviewer.auth import schemas as auth_schemas
from ai_interviewer.auth import security
from ai_interviewer.models.user_models import User, UserRole # For response models and current_user typing
from ai_interviewer.auth.config import settings as auth_settings

# Dependency to get the database (should be defined in server.py or a core dependencies file)
# For now, we assume it will be correctly injected when the router is included.
# We need to ensure server.py provides get_motor_db correctly.
from ai_interviewer.core.database import get_motor_db # Ensure this path is correct

import logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/register", response_model=auth_schemas.UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_create: auth_schemas.UserCreate, 
    db: AsyncIOMotorDatabase = Depends(get_motor_db)
):
    """
    Register a new user.
    - Default role will be CANDIDATE.
    - Email must be unique.
    """
    logger.info(f"Attempting to register user: {user_create.email}")
    try:
        # Ensure default role if not provided, or validate provided roles
        if not user_create.roles:
            user_create.roles = [UserRole.CANDIDATE]
        
        created_user = await auth_services.create_user_service(user_create_data=user_create, db=db)
        logger.info(f"User {created_user.email} registered successfully with ID: {created_user.id}")
        return created_user
    except ValueError as ve: # Catch specific error from create_user_service (e.g., email exists)
        logger.warning(f"Registration failed for {user_create.email}: {ve}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve),
        )
    except Exception as e:
        logger.error(f"Unexpected error during registration for {user_create.email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during registration.",
        )

@router.post("/token", response_model=auth_schemas.Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: AsyncIOMotorDatabase = Depends(get_motor_db)
):
    """
    Provide an access token for a user.
    - Uses OAuth2PasswordRequestForm (username = email, password).
    """
    logger.info(f"Login attempt for username: {form_data.username}")
    user = await auth_services.authenticate_user_service(
        email=form_data.username, password=form_data.password, db=db
    )
    if not user:
        logger.warning(f"Login failed for username: {form_data.username}. Invalid credentials.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        logger.warning(f"Login failed for username: {form_data.username}. User is inactive.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    
    access_token = security.create_access_token(
        data={"user_id": str(user.id), "roles": [role.value for role in user.roles]} # Store user_id and roles
    )
    logger.info(f"Login successful for {user.email}. Token generated.")
    return {"access_token": access_token, "token_type": "bearer", "user_id": str(user.id), "email": user.email, "roles": user.roles}

@router.get("/users/me", response_model=auth_schemas.UserResponse)
async def read_users_me(
    current_user: Annotated[User, Depends(security.get_current_active_user)]
):
    """
    Get current authenticated user's details.
    """
    logger.info(f"Fetching details for current user: {current_user.email}")
    return current_user

@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(
    request_body: auth_schemas.PasswordResetRequest,
    db: AsyncIOMotorDatabase = Depends(get_motor_db)
):
    logger.info(f"Password reset requested for email: {request_body.email}")
    token = await auth_services.create_password_reset_token_service(email=request_body.email, db=db)
    if not token:
        # Still return 200 to prevent email enumeration, but log it
        logger.warning(f"Password reset token requested for non-existent or inactive user: {request_body.email}")
        return {"msg": "If an account with this email exists, a password reset link has been sent."}

    # In a real app, you would email this token to the user.
    # For now, we can log it or return it for testing if in a dev environment.
    logger.info(f"Password reset token generated for {request_body.email}. Token: {token} (This would be emailed)")
    # DO NOT return the token in production. This is for demonstration/testing.
    # In a real app, send an email with a link like: https://yourdomain.com/reset-password?token={token}
    return {"msg": "If an account with this email exists, a password reset token has been generated.", "reset_token_for_testing": token}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    request_body: auth_schemas.PasswordResetConfirm,
    db: AsyncIOMotorDatabase = Depends(get_motor_db)
):
    logger.info(f"Attempting to reset password with token: {request_body.token[:10]}...") # Log part of token
    success = await auth_services.reset_password_with_token_service(
        token=request_body.token, 
        new_password=request_body.new_password, 
        db=db
    )
    if not success:
        logger.warning(f"Password reset failed for token: {request_body.token[:10]}... Invalid or expired token.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token."
        )
    logger.info(f"Password successfully reset for token: {request_body.token[:10]}...")
    return {"msg": "Password has been reset successfully."}

# Example of a protected route requiring a specific role
@router.get("/users", response_model=List[auth_schemas.UserResponse], dependencies=[Depends(security.RoleChecker([UserRole.ADMIN]))])
async def read_all_users(
    db: AsyncIOMotorDatabase = Depends(get_motor_db),
    # current_user: Annotated[User, Depends(security.get_current_admin_user)] # Or a specific admin dependency
):
    """
    Get all users. (Admin only)
    """
    logger.info("Admin request to read all users.")
    users = await auth_services.get_all_users_service(db=db)
    return users

@router.put("/users/{user_id}/roles", response_model=auth_schemas.UserResponse, dependencies=[Depends(security.RoleChecker([UserRole.ADMIN]))])
async def update_user_roles(
    user_id: str,
    roles_update: auth_schemas.UserRolesUpdate,
    db: AsyncIOMotorDatabase = Depends(get_motor_db),
    # current_admin: User = Depends(security.get_current_admin_user) # Ensure admin
):
    """
    Update roles for a specific user. (Admin only)
    """
    logger.info(f"Admin request to update roles for user ID {user_id} to {roles_update.roles}")
    updated_user = await auth_services.update_user_roles_service(user_id=user_id, roles=roles_update.roles, db=db)
    if not updated_user:
        logger.warning(f"Failed to update roles for user ID {user_id}. User not found.")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    logger.info(f"Successfully updated roles for user ID {user_id}.")
    return updated_user

# Make sure security.py has create_access_token (not create_access_token_for_user)
# and it accepts `data: dict` 