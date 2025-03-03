import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_schema_exists(async_session):
    """Test that the test_schema exists and is being used."""
    # Start a transaction for this test
    async with async_session.begin():
        # Set the search path to test_schema explicitly for this transaction
        await async_session.execute(text("SET search_path TO test_schema"))
        
        # Check if test_schema is in the search path
        result = await async_session.execute(text("SHOW search_path"))
        search_path = result.scalar()
        assert "test_schema" in search_path, f"test_schema not in search path: {search_path}"
        
        # Verify that the current schema is test_schema
        result = await async_session.execute(text("SELECT current_schema()"))
        current_schema = result.scalar()
        assert current_schema == "test_schema", f"Current schema is {current_schema}, not test_schema"
        
        # Check if the tables exist in test_schema
        result = await async_session.execute(
            text("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'test_schema'
            ORDER BY table_name
            """)
        )
        tables = [row[0] for row in result.fetchall()]
        
        # Assert that the expected tables exist
        assert "projects" in tables, f"projects table not found in test_schema. Found tables: {tables}"
        assert "batches" in tables, f"batches table not found in test_schema. Found tables: {tables}"
        assert "project_patches" in tables, f"project_patches table not found in test_schema. Found tables: {tables}"
        
        # The transaction will be rolled back automatically at the end of the test 