"""Use the caller's transaction for both CLI and application migrations."""
from alembic import context
from sqlalchemy import create_engine
from db import DATABASE_URL


def run(connection):
    context.configure(connection=connection, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


connection = context.config.attributes.get("connection")
if connection is not None:
    run(connection)
else:
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        run(connection)
