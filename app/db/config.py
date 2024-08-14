from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncEngine,
    async_sessionmaker,
    AsyncAttrs,
)
from sqlalchemy.orm import DeclarativeBase

from ..core.config import settings

SQLALCHEMY_DATABASE_URL = settings.database_url

async_engine: AsyncEngine = create_async_engine(
    SQLALCHEMY_DATABASE_URL, echo=False  # "debug" if settings.debug else False
)

AsyncSessionLocal = async_sessionmaker(bind=async_engine, autoflush=False)


# Base class for declarative_base
class Base(AsyncAttrs, DeclarativeBase):
    pass
