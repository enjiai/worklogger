import asyncio
import logging
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy import text, MetaData
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from models import Base, mapper_registry
from settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create async database URL
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')


# Use pytest-asyncio's event_loop_policy fixture instead of defining our own event_loop
@pytest.fixture(scope="session")
def event_loop_policy():
    """Return the event loop policy to use."""
    return asyncio.get_event_loop_policy()


@pytest_asyncio.fixture(scope="session")
async def async_engine():
    """Create a new async engine for the tests."""
    # Use NullPool to avoid connection pooling issues
    engine = create_async_engine(
        ASYNC_DATABASE_URL, 
        echo=False, 
        future=True,
        poolclass=NullPool
    )
    
    # Set the schema for the metadata to test_schema for the test environment
    # Create a new metadata with the schema set to test_schema
    metadata = MetaData(schema="test_schema")
    # Update the Base.metadata with the new schema
    for table in list(Base.metadata.tables.values()):
        # Clone the table with the new schema
        table.schema = "test_schema"
    
    logger.info(f"Set schema for all tables to test_schema")
    
    async with engine.begin() as conn:
        # Ensure test_schema exists
        result = await conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'test_schema'"))
        schema_exists = result.scalar() is not None
        
        if not schema_exists:
            logger.info("Creating test_schema for tests...")
            await conn.execute(text("CREATE SCHEMA test_schema"))
        else:
            logger.info("test_schema already exists")
        
        # Grant privileges
        await conn.execute(text(f"GRANT ALL ON SCHEMA test_schema TO {settings.DB_USER}"))
        logger.info(f"Granted all privileges on test_schema to {settings.DB_USER}")
        
        # Set search path to test_schema
        await conn.execute(text("SET search_path TO test_schema"))
        logger.info("Set search path to test_schema")
        
        # Drop all existing tables in test_schema to start fresh
        logger.info("Dropping all existing tables in test_schema...")
        await conn.execute(text("""
            DO $$ 
            DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'test_schema') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS test_schema.' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """))
        
        # Create all tables in test_schema
        logger.info("Creating all tables in test_schema...")
        # Explicitly set the schema in the create_all call
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))
        
        # Verify tables were created
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'test_schema'"
        ))
        tables = result.scalars().all()
        logger.info(f"Tables created in test_schema: {tables}")
    
    yield engine
    
    # No cleanup after tests - we want to preserve the data
    
    # Reset the schema for the tables back to public
    for table in list(Base.metadata.tables.values()):
        table.schema = settings.DB_SCHEMA
    logger.info(f"Reset schema for all tables to {settings.DB_SCHEMA}")
    
    await engine.dispose()


@pytest.fixture
async def async_session(async_engine):
    """
    Create a new SQLAlchemy AsyncSession for a test.
    """
    logger.info("Creating async session")
    
    # Create a session factory
    async_session_factory = async_sessionmaker(
        async_engine,
        expire_on_commit=False,
        autobegin=False,  # Don't automatically begin a transaction
    )
    
    # Create a session
    session = async_session_factory()
    
    try:
        # Start a transaction for setting the search path
        async with session.begin():
            # Set the search path to test_schema
            await session.execute(text("SET search_path TO test_schema"))
            logger.info("Session created with search path set to test_schema")
        
        # Yield the session for the test to use
        # Tests will manage their own transactions
        yield session
        
    finally:
        # Close the session
        await session.close()
        logger.info("Session closed") 