import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.core.config import settings
# from app.models.merchant import Base as MerchantBase
# from app.models.bill import Base as BillBase
from app.models.merchant import Base

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

target_metadata = Base.metadata
# target_metadata = MerchantBase.metadata
# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config
raw_url = settings.DATABASE_URL
parsed = urlparse(raw_url)
# 1. Change protocol
new_scheme = "postgresql+asyncpg"

# 2. Parse out the query parameters
query_params = parse_qs(parsed.query)

# 3. Handle SSL logic strictly
# Map 'sslmode' to asyncpg's expected 'ssl'
ssl_val = None
if 'sslmode' in query_params:
    mode = query_params.pop('sslmode')[0]
    if mode in ['require', 'verify-ca', 'verify-full']:
        ssl_val = 'true'

# 4. Remove other problematic keys
query_params.pop('channel_binding', None)

# 5. Add our clean 'ssl' param back if needed
if ssl_val:
    query_params['ssl'] = [ssl_val]

# 6. Rebuild the URL
new_query = urlencode(query_params, doseq=True)
db_url = urlunparse(parsed._replace(scheme=new_scheme, query=new_query))

config.set_main_option("sqlalchemy.url", db_url)

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
# target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    section = config.get_section(config.config_ini_section, {})
    url_string = config.get_main_option("sqlalchemy.url")
    use_ssl = "ssl=true" in url_string

    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"ssl": True} if use_ssl else {},
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
