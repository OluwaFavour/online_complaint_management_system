import cloudinary

from passlib.context import CryptContext
from pydantic_settings import BaseSettings, SettingsConfigDict
from fastapi.security import OAuth2PasswordBearer


class Settings(BaseSettings):
    access_token_expiry_minutes: int = 15
    admin_email: str
    admin_username: str
    admin_password: str
    app_name: str = "Online Complaint Management System"
    app_version: str = "0.0.1"
    cloudinary_url: str
    cors_allowed_methods: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    cors_allow_credentials: bool
    cors_allowed_origins: list[str]
    database_url: str
    debug: bool = False
    from_email: str
    from_name: str = "Online Complaint Management System"
    frontend_url: str
    host_servers: list[dict[str, str]] = [
        {"url": "http://127.0.0.1:8000", "description": "localhost"}
    ]
    jwt_algorithm: str = "HS256"
    jwt_secret_key: str
    otp_expiry_minutes: int = 5
    refresh_token_expiry_days: int = 7
    reset_token_expiry_minutes: int = 5
    smtp_host: str
    smtp_login: str
    smtp_password: str
    smtp_port: int

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


# Cloudinary configuration parser
def cloudinary_config_parser(cloudinary_url: str) -> dict[str, str]:
    """
    Parses the Cloudinary URL and extracts the cloud name, API key, and API secret.

    Args:
        cloudinary_url (str): The Cloudinary URL to parse.

    Returns:
        dict[str, str]: A dictionary containing the cloud name, API key, and API secret.
    """
    cloudinary_config = {}
    cloudinary_url = cloudinary_url.split("://")[1]
    cloudinary_config["cloud_name"] = cloudinary_url.split("@")[1].split(".")[0]
    cloudinary_config["api_key"] = cloudinary_url.split("@")[0].split(":")[0]
    cloudinary_config["api_secret"] = cloudinary_url.split("@")[0].split(":")[1]
    return cloudinary_config


# Cloudinary configuration
config_data = cloudinary_config_parser(settings.cloudinary_url)
config = cloudinary.config(
    cloud_name=config_data["cloud_name"],
    api_key=config_data["api_key"],
    api_secret=config_data["api_secret"],
    secret=True,
)
