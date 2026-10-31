from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

DATABASE_URL = settings.database_url
async_engine = create_async_engine(DATABASE_URL, echo=settings.sql_echo, hide_parameters=True, pool_pre_ping=True,
                                   pool_size=5, max_overflow=10, pool_timeout=10,
                                   connect_args={'command_timeout': 30})
async_session_maker = async_sessionmaker(async_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass
