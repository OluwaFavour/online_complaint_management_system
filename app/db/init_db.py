from .models import Base
from .config import async_engine


async def init_db():
    """
    Initializes the database by creating all the tables defined in the metadata.

    Returns:
        None
    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db():
    """
    Dispose the database connection.

    This function is responsible for disposing the database connection by calling the `dispose()` method of the `async_engine` object.

    Parameters:
        None

    Returns:
        None
    """
    await async_engine.dispose()


async def drop_db():
    """
    Drops all tables in the database.

    This function uses the `async_engine` to connect to the database and drops all tables defined in the `Base.metadata`.

    Raises:
        Any exceptions raised by the underlying database engine.

    """
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
