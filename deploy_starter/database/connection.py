import os

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
)

from core.config import config

import database.models  # noqa: F401

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or config.get("DATABASE_URL")
)


if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not configured."
    )


engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True, #从连接池取出连接准备使用前，先检查连接是否还有效。
    pool_size=int(os.getenv("DATABASE_POOL_SIZE", config.get("DATABASE_POOL_SIZE", 5))),
    max_overflow=int(
        os.getenv("DATABASE_MAX_OVERFLOW", config.get("DATABASE_MAX_OVERFLOW", 10))
    ),
)


AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
)
