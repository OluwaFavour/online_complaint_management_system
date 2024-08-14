from passlib.context import CryptContext
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi.security import OAuth2PasswordBearer


class Settings(BaseSettings):
    access_token_expiry_minutes: int = 15
    admin_email: str
    admin_username: str
    admin_password: str
    app_name: str = "Online Complaint Management System"
    app_version: str = "0.1.0"
    cors_allowed_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    cors_allow_credentials: bool
    cors_allowed_origins: list[str]
    database_url: str
    debug: bool = False
    jwt_algorithm: str = "HS256"
    jwt_secret_key: str
    refresh_token_expiry_days: int = 7

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")
