from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# 1. Get database URL from settings
url = settings.database_url

# 2. Fix URL prefix for SQLAlchemy + psycopg2 compatibility
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg2://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

# 3. Configure connection arguments based on database engine
connect_args = {}
if url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# 4. Initialize Engine and Session
engine = create_engine(url, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()