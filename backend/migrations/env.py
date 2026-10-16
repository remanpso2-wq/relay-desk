import os
from alembic import context
from sqlalchemy import create_engine
from app.db import Base

config = context.config
url = os.getenv("DATABASE_URL", "sqlite:///./relay.db")
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with create_engine(url).connect() as connection:
        context.configure(
            connection=connection, target_metadata=Base.metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
