from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    SECRET_KEY: str = "a_very_secret_key_that_should_be_in_env" # Load from .env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    API_V1_STR: str = "/api/v1" # Or your chosen API prefix
    MONGO_USERS_COLLECTION: str = "users" # Default collection name for users
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30 # Default expiry for reset tokens

    # Refresh Token Settings
    REFRESH_SECRET_KEY: str = "a_very_secret_refresh_key_that_should_be_in_env" # Load from .env
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7 # Expiry for refresh tokens (e.g., 7 days)
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"

    # OAuth Provider Settings (placeholders, load from .env)
    GOOGLE_OAUTH_CLIENT_ID: str = "YOUR_GOOGLE_CLIENT_ID"
    GOOGLE_OAUTH_CLIENT_SECRET: str = "YOUR_GOOGLE_CLIENT_SECRET"
    GOOGLE_OAUTH_REDIRECT_URI: str = f"{API_V1_STR}/auth/oauth/google/callback" # Example, adjust as needed

    GITHUB_OAUTH_CLIENT_ID: str = "YOUR_GITHUB_CLIENT_ID"
    GITHUB_OAUTH_CLIENT_SECRET: str = "YOUR_GITHUB_CLIENT_SECRET"
    GITHUB_OAUTH_REDIRECT_URI: str = f"{API_V1_STR}/auth/oauth/github/callback" # Example, adjust as needed

    # Frontend URL (for redirecting after successful OAuth login)
    FRONTEND_URL: str = "http://localhost:3000" # Adjust to your frontend's URL

    # MongoDB settings (if not already globally configured) 

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
