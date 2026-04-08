from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

_backend_dir = Path(__file__).parent.parent.parent
_root_dir = _backend_dir.parent
_backend_env = _backend_dir / ".env"
_root_env = _root_dir / ".env"
_env_file = str(_backend_env) if _backend_env.exists() else str(_root_env) if _root_env.exists() else None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    DOMAIN_DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/stellantis"


settings = Settings()

engine = create_async_engine(settings.DOMAIN_DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass
