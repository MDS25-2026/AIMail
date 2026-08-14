"""SQLAlchemy declarative base. Import-safe: no engine, no environment access."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
