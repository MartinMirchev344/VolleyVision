"""Connection settings come only from the environment, never from committed credentials."""

from alembic import context
from sqlalchemy import create_engine, pool

from volleyvision.db import Base, database_url

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    context.configure(
        connection=context.config.attributes["connection"], target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(
        database_url(), poolclass=pool.NullPool, connect_args={"connect_timeout": 5}
    )
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
