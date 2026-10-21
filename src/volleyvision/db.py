"""PostgreSQL bootstrap; feature models arrive with their first migration."""

import os

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def database_url(variable: str = "DATABASE_URL") -> str:
    value = os.environ.get(variable, "")
    if not value:
        raise ValueError(f"Set {variable} to a PostgreSQL connection URL.")
    try:
        parsed = make_url(value)
    except Exception:
        raise ValueError(f"{variable} is not a valid connection URL.") from None
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError(f"{variable} must use the postgresql+psycopg driver.")
    return value


def check_database() -> dict:
    engine = create_engine(database_url(), connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            version = connection.scalar(text("SHOW server_version"))
            result = connection.scalar(text("SELECT 1"))
        return {"connected": result == 1, "server_version": version}
    finally:
        engine.dispose()
