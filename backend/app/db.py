from urllib.parse import urlparse, urlunparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

# Convert postgresql:// to postgresql+asyncpg:// and strip query string
# asyncpg does not understand ?sslmode=require&channel_binding=require;
# SSL is passed via connect_args instead.
_parsed = urlparse(settings.DATABASE_URL)
_clean_url = urlunparse(_parsed._replace(scheme="postgresql+asyncpg", query=""))

engine = create_async_engine(
    _clean_url,
    echo=False,
    connect_args={"ssl": "require"},
    pool_pre_ping=True,  # Neon drops idle pooled connections; validate before use
    pool_recycle=300,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
