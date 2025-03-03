#!/usr/bin/env python
import asyncio
import logging
import os
import subprocess
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def ensure_test_schema_exists():
    """Ensure the test_schema exists before running tests."""
    # Create an async engine using the settings
    async_db_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
    logger.info(f"Connecting to database: {async_db_url}")
    
    # Use NullPool to avoid connection pooling issues
    engine = create_async_engine(
        async_db_url,
        poolclass=NullPool,
        future=True
    )
    
    try:
        async with engine.begin() as conn:
            # Check if the schema exists
            result = await conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'test_schema'"))
            schema_exists = result.scalar() is not None
            
            if not schema_exists:
                logger.info("Creating test_schema...")
                await conn.execute(text("CREATE SCHEMA test_schema"))
                logger.info("test_schema created successfully")
            else:
                logger.info("test_schema already exists")
                
            # Grant privileges to the current user
            current_user = settings.DB_USER
            await conn.execute(text(f"GRANT ALL ON SCHEMA test_schema TO {current_user}"))
            logger.info(f"Granted all privileges on test_schema to {current_user}")
            
    except Exception as e:
        logger.error(f"Error creating test_schema: {e}")
        raise
    finally:
        await engine.dispose()


def run_tests():
    """Run pytest with the specified arguments."""
    logger.info("Running tests...")
    
    # Get command line arguments, excluding the script name
    pytest_args = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Add default arguments if none provided
    if not pytest_args:
        pytest_args = ["tests/"]
    
    # Run pytest with the provided arguments
    cmd = ["pytest", "-v"] + pytest_args
    logger.info(f"Running command: {' '.join(cmd)}")
    
    result = subprocess.run(cmd)
    return result.returncode


if __name__ == "__main__":
    logger.info("Starting test runner")
    
    # Create a new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Ensure test_schema exists
        loop.run_until_complete(ensure_test_schema_exists())
        
        # Run the tests
        exit_code = run_tests()
        
        # Exit with the pytest return code
        sys.exit(exit_code)
    finally:
        # Clean up the event loop
        loop.close() 