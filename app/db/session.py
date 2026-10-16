from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.settings import Settings


class Database:
    def __init__(self, settings: Settings):
        self.engine = create_async_engine(
            settings.database_url.get_secret_value(),
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={
                "timeout": 5,
                "server_settings": {
                    "statement_timeout": str(settings.db_statement_timeout_ms),
                    "idle_in_transaction_session_timeout": "30000",
                },
            },
        )
        self.sessions = async_sessionmaker(
            self.engine, expire_on_commit=False, autoflush=False
        )

    async def close(self) -> None:
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # Closing the session rolls back any uncommitted transaction and returns its connection.
    async with request.app.state.database.sessions() as session:
        yield session

async def db_for_celery()