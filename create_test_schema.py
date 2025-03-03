import logging
import asyncio
import sqlalchemy
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from settings import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def create_test_schema():
    """
    Create the test_schema in the database if it doesn't exist.
    Uses the database credentials from the settings module.
    """
    # Create an async engine using the settings
    # Convert the standard PostgreSQL URL to an async one
    async_db_url = settings.DATABASE_URL.replace('postgresql://', 'postgresql+asyncpg://')
    logger.info(f"Connecting to database: {async_db_url}")
    
    engine = create_async_engine(async_db_url)
    
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
            
            # Set the search path to include test_schema
            await conn.execute(text("SET search_path TO test_schema, public"))
            logger.info("Search path updated to include test_schema")
            
    except Exception as e:
        logger.error(f"Error creating test_schema: {e}")
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    logger.info("Starting test_schema creation process")
    asyncio.run(create_test_schema())
    logger.info("Test schema creation process completed") 