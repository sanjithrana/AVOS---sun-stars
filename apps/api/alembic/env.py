import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.database.base import Base
from src.database.models.asset import Asset
from src.database.models.job import JobRecord
from src.database.models.project import Project
from src.database.models.qa import QAResult
from src.database.models.repair import RepairPlan
from src.database.models.shot import Shot
from src.database.models.audit import AuditRecord
from src.database.models.human_gate import HumanGate
from src.database.models.shot_version import ShotVersion
from src.database.models.world_state import WorldStateRecord

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Prefer DATABASE_URL from the environment (docker-compose sets it; so
# does a local dev shell). Without this, alembic always used the
# hardcoded host "postgres" from alembic.ini, so `alembic upgrade head`
# only worked from inside the api container.
_database_url = os.getenv("DATABASE_URL")
if _database_url:
    config.set_main_option("sqlalchemy.url", _database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
