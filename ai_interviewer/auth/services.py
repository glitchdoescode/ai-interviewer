from typing import Optional, List
from pydantic import EmailStr
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection
from datetime import datetime, timedelta, timezone
from bson import ObjectId # For handling MongoDB's ObjectId
import secrets # Restored secrets

from ai_interviewer.models.user_models import User, UserCreate as UserModelUserCreate, UserInDB, UserRole
from ai_interviewer.auth.schemas import UserCreate as SchemaUserCreate # Distinguish UserCreate from schemas
from ai_interviewer.auth.password_utils import get_password_hash, verify_password
from ai_interviewer.utils.config import get_db_config
from ai_interviewer.auth.config import settings as auth_settings # Restored auth_settings

async def get_user_collection(db: AsyncIOMotorDatabase) -> AsyncIOMotorCollection:
    """Helper function to get the users collection from the database."""
    db_config = get_db_config()
    users_collection_name = db_config.get("users_collection", "users")
    return db[users_collection_name]

async def get_user_by_email_service(email: str, db: AsyncIOMotorDatabase) -> Optional[UserInDB]:
    """Retrieves a user by their email address from the services layer."""
    users_coll = await get_user_collection(db)
    user_doc = await users_coll.find_one({"email": email})
    if user_doc:
        if "_id" in user_doc and isinstance(user_doc["_id"], ObjectId):
            user_doc["_id"] = str(user_doc["_id"])
        if "roles" in user_doc and isinstance(user_doc["roles"], list):
            try:
                user_doc["roles"] = [UserRole(role) for role in user_doc["roles"]]
            except ValueError:
                pass 
        return UserInDB(**user_doc)
    return None

async def get_user_by_id_service(user_id: str, db: AsyncIOMotorDatabase) -> Optional[UserInDB]:
    """Retrieves a user by their ID from the services layer."""
    users_coll = await get_user_collection(db)
    try:
        obj_id = ObjectId(user_id) # Validate input user_id can be ObjectId
    except Exception:
        return None # Invalid ObjectId format for input user_id
    
    user_doc = await users_coll.find_one({"_id": obj_id})
    if user_doc:
        if "_id" in user_doc and isinstance(user_doc["_id"], ObjectId):
            user_doc["_id"] = str(user_doc["_id"])

        if "roles" in user_doc and isinstance(user_doc["roles"], list):
            try:
                user_doc["roles"] = [UserRole(role) for role in user_doc["roles"]]
            except ValueError:
                pass
        return UserInDB(**user_doc)
    return None

async def create_user_service(user_create_data: SchemaUserCreate, db: AsyncIOMotorDatabase) -> User:
    """Creates a new user in the database via the services layer."""
    users_coll = await get_user_collection(db)
    
    existing_user = await get_user_by_email_service(user_create_data.email, db)
    if existing_user:
        raise ValueError(f"User with email {user_create_data.email} already exists.")

    hashed_password_for_db: Optional[str] = None
    if user_create_data.password:
        hashed_password_for_db = get_password_hash(user_create_data.password)
    # If password is not provided (e.g. OAuth), hashed_password_for_db remains None.
    # UserInDB model now supports hashed_password: Optional[str]

    user_doc_to_insert = {
        "email": user_create_data.email,
        "full_name": user_create_data.full_name, # From SchemaUserCreate
        "is_active": user_create_data.is_active,
        "roles": [role.value for role in user_create_data.roles],
        "hashed_password": hashed_password_for_db 
    }
    # Do not include "_id" or "id", MongoDB will generate it.
    
    result = await users_coll.insert_one(user_doc_to_insert)
    
    created_user_doc = await users_coll.find_one({"_id": result.inserted_id})
    if not created_user_doc:
        # This should ideally not happen if insert_one was successful
        raise Exception("Failed to create user or retrieve after creation.")

    # No need to manually convert _id to id or str if Pydantic model_config handles it
    # with alias and json_encoders for ObjectId if _id is kept as ObjectId in Pydantic model field.
    # However, our User model expects id as Optional[str] and aliases _id.
    # So, ensuring created_user_doc has "_id" as a string for User(**created_user_doc) is good. 
    if "_id" in created_user_doc and isinstance(created_user_doc["_id"], ObjectId):
         created_user_doc["_id"] = str(created_user_doc["_id"])

    if "roles" in created_user_doc and isinstance(created_user_doc["roles"], list):
        try:
            created_user_doc["roles"] = [UserRole(role) for role in created_user_doc["roles"]]
        except ValueError:
            pass 
            
    # User model (from user_models.py) is used for the response type.
    # It has id = Field(alias="_id") and from_attributes=True, populate_by_name=True
    # It will correctly map the database document (including _id) to the User Pydantic model.
    return User(**created_user_doc)

async def authenticate_user_service(email: str, password: str, db: AsyncIOMotorDatabase) -> Optional[User]:
    """Authenticates a user by email and password."""
    user_in_db = await get_user_by_email_service(email, db)
    if not user_in_db:
        return None
    
    # If hashed_password is None in DB (e.g. OAuth user), verification should fail for password login
    if user_in_db.hashed_password is None:
        return None 
        
    if not verify_password(password, user_in_db.hashed_password):
        return None
    # Return the User model (which doesn't expose hashed_password)
    return User(**user_in_db.model_dump(exclude={"hashed_password"}))

async def get_password_reset_token_collection(db: AsyncIOMotorDatabase) -> AsyncIOMotorCollection:
    """Helper function to get the password_reset_tokens collection."""
    db_config = get_db_config()
    collection_name = db_config.get("password_reset_tokens_collection", "password_reset_tokens")
    return db[collection_name]

async def create_password_reset_token_service(email: str, db: AsyncIOMotorDatabase) -> Optional[str]:
    """Creates a password reset token for a user if they exist."""
    user_in_db = await get_user_by_email_service(email=email, db=db) # Use UserInDB to check details
    if not user_in_db or not user_in_db.id or not user_in_db.is_active:
        return None # User doesn't exist or is not active

    token = secrets.token_urlsafe(32)
    expires_delta = timedelta(minutes=auth_settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.now(timezone.utc) + expires_delta
    
    reset_tokens_coll = await get_password_reset_token_collection(db)
    
    await reset_tokens_coll.insert_one({
        "user_id": str(user_in_db.id), # Store user.id as string
        "token": token,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc)
    })
    
    return token

async def reset_password_with_token_service(token: str, new_password: str, db: AsyncIOMotorDatabase) -> bool:
    """Resets a user's password using a valid reset token."""
    reset_tokens_coll = await get_password_reset_token_collection(db)
    
    token_doc = await reset_tokens_coll.find_one({"token": token})
    
    if not token_doc:
        return False 
        
    if datetime.now(timezone.utc) > token_doc["expires_at"]:
        await reset_tokens_coll.delete_one({"_id": token_doc["_id"]})
        return False 
        
    user_id_from_token = token_doc.get("user_id")
    if not user_id_from_token:
        # Invalid token document structure
        await reset_tokens_coll.delete_one({"_id": token_doc["_id"]}) # Clean up bad token
        return False 

    new_hashed_password = get_password_hash(new_password)
    
    users_coll = await get_user_collection(db)
    
    # Ensure user_id_from_token is valid ObjectId if your DB uses ObjectIds for _id
    try:
        user_obj_id = ObjectId(user_id_from_token)
    except Exception:
        # Invalid ObjectId format in token, critical error or bad token data
        await reset_tokens_coll.delete_one({"_id": token_doc["_id"]}) # Clean up
        return False

    update_result = await users_coll.update_one(
        {"_id": user_obj_id},
        {"$set": {"hashed_password": new_hashed_password}}
    )
    
    if update_result.matched_count == 0:
        # User ID from token didn't match any user, possibly deleted after token generation
        await reset_tokens_coll.delete_one({"_id": token_doc["_id"]})
        return False
        
    # Successfully updated password, delete the token
    await reset_tokens_coll.delete_one({"_id": token_doc["_id"]})
    
    return True

async def get_all_users_service(db: AsyncIOMotorDatabase) -> List[User]:
    """Retrieves all users from the database."""
    users_coll = await get_user_collection(db)
    users_cursor = users_coll.find()
    users_list: List[User] = []
    async for user_doc in users_cursor:
        if "_id" in user_doc and isinstance(user_doc.get("_id"), ObjectId):
            user_doc["_id"] = str(user_doc["_id"])
        if "roles" in user_doc and isinstance(user_doc["roles"], list):
            try:
                user_doc["roles"] = [UserRole(role) for role in user_doc["roles"]]
            except ValueError: 
                user_doc["roles"] = [UserRole.CANDIDATE] # Default or log error
        users_list.append(User(**user_doc))
    return users_list

async def update_user_roles_service(user_id: str, roles: List[UserRole], db: AsyncIOMotorDatabase) -> Optional[User]:
    """Updates the roles for a specific user by their ID."""
    users_coll = await get_user_collection(db)
    
    role_values = [role.value for role in roles]
    try:
        user_obj_id = ObjectId(user_id)
    except Exception:
        return None # Invalid user_id format
    
    update_result = await users_coll.update_one(
        {"_id": user_obj_id},
        {"$set": {"roles": role_values}}
    )
    
    if update_result.matched_count == 0:
        return None 
        
    updated_user_doc = await users_coll.find_one({"_id": user_obj_id})
    if updated_user_doc:
        if "_id" in updated_user_doc and isinstance(updated_user_doc.get("_id"), ObjectId):
           updated_user_doc["_id"] = str(updated_user_doc["_id"])
        if "roles" in updated_user_doc and isinstance(updated_user_doc["roles"], list):
            try:
                updated_user_doc["roles"] = [UserRole(role) for role in updated_user_doc["roles"]]
            except ValueError:
                pass # Pydantic will validate
        return User(**updated_user_doc)
    return None
