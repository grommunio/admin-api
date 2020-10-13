from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

from orm import DB, _loadDBConfig

def loadSchema():
    from orm import ext, misc, orgs, roles, users


target_metadata = DB.metadata
loadSchema()

def run_migrations_offline():
    url = _loadDBConfig()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = DB.engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
