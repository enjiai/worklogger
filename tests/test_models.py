import logging
import uuid
from sqlalchemy import text, select
import pytest

from models import Project, ProjectPatch, Batch, BatchProjectPatch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@pytest.mark.asyncio
async def test_project_model(async_session):
    """Test the Project model in the test_schema."""
    # Start a transaction for this test
    async with async_session.begin():
        # Ensure we're in the test_schema
        await async_session.execute(text("SET search_path TO test_schema"))
        logger.info("Set search path to test_schema")
    
        # Verify the current schema
        result = await async_session.execute(text("SELECT current_schema()"))
        current_schema = result.scalar()
        logger.info(f"Current schema: {current_schema}")
    
        # Create a test project with a unique name to avoid conflicts
        unique_id = str(uuid.uuid4())
        unique_name = f"Test Project {unique_id}"
        project = Project(name=unique_name, settings={"key": "value"}, enabled=True)
        async_session.add(project)
        await async_session.flush()
        logger.info(f"Created project with ID: {project.id} and name: {unique_name}")
    
        # Verify the project exists in the database
        result = await async_session.execute(text(f"SELECT COUNT(*) FROM projects WHERE name = '{unique_name}'"))
        count = result.scalar()
        assert count == 1, f"Project {unique_name} not found in the database"
        logger.info(f"Verified project exists in the database with count: {count}")
    
        # Create a patch for the project
        patch = ProjectPatch(
            project_id=project.id,
            branch_name="main",
            patch="test patch content",
            processed=False
        )
        async_session.add(patch)
        await async_session.flush()
        logger.info(f"Created patch with ID: {patch.id} for project ID: {project.id}")
    
        # Query the project using SQLAlchemy ORM
        stmt = select(Project).where(Project.name == unique_name)
        result = await async_session.execute(stmt)
        db_project = result.scalars().first()
        assert db_project is not None, f"Project {unique_name} not found using SQLAlchemy ORM"
        assert db_project.id == project.id, f"Project ID mismatch: {db_project.id} != {project.id}"
        logger.info(f"Verified project can be queried using SQLAlchemy ORM: {db_project.name}")
    
        # Query the patch using SQLAlchemy ORM
        stmt = select(ProjectPatch).where(ProjectPatch.project_id == project.id)
        result = await async_session.execute(stmt)
        db_patch = result.scalars().first()
        assert db_patch is not None, f"Patch for project {project.id} not found using SQLAlchemy ORM"
        assert db_patch.id == patch.id, f"Patch ID mismatch: {db_patch.id} != {patch.id}"
        logger.info(f"Verified patch can be queried using SQLAlchemy ORM: {db_patch.patch}")
    
        # The transaction will be rolled back automatically at the end of the test


@pytest.mark.asyncio
async def test_model_relationships(async_session):
    """Test relationships between models in the test_schema."""
    # Start a transaction for this test
    async with async_session.begin():
        # Ensure we're in the test_schema
        await async_session.execute(text("SET search_path TO test_schema"))
        logger.info("Set search path to test_schema")
    
        # Create a unique identifier for this test run
        unique_id = str(uuid.uuid4())
    
        # Create a test project
        project_name = f"Relationship Test Project {unique_id}"
        project = Project(name=project_name, settings={"key": "value"}, enabled=True)
        async_session.add(project)
        await async_session.flush()
        logger.info(f"Created project with ID: {project.id} and name: {project_name}")
    
        # Create a batch associated with the project
        batch_name = f"Test Batch {unique_id}"
        batch = Batch(
            name=batch_name,
            is_active=True,
            is_processed=False,
            project_id=project.id
        )
        async_session.add(batch)
        await async_session.flush()
        logger.info(f"Created batch with ID: {batch.id} and name: {batch_name}")
    
        # Verify the batch was created with the correct name using a direct SQL query
        result = await async_session.execute(
            text(f"SELECT name FROM batches WHERE id = {batch.id}")
        )
        db_batch_name = result.scalar()
        assert db_batch_name == batch_name, f"Batch name mismatch: {db_batch_name} != {batch_name}"
        logger.info(f"Verified batch name in database: {db_batch_name}")
    
        # Create a patch for the project
        patch_content = f"Test Patch Content {unique_id}"
        patch = ProjectPatch(
            project_id=project.id,
            branch_name="main",
            patch=patch_content,
            processed=False
        )
        async_session.add(patch)
        await async_session.flush()
        logger.info(f"Created patch with ID: {patch.id} for project ID: {project.id}")
    
        # Create a relationship between the batch and the patch
        batch_patch = BatchProjectPatch(
            batch_id=batch.id,
            patch_id=patch.id
        )
        async_session.add(batch_patch)
        await async_session.flush()
        logger.info(f"Created batch_patch relationship with batch_id: {batch.id} and patch_id: {patch.id}")
    
        # Verify the relationship was created using a direct SQL query
        result = await async_session.execute(
            text(f"SELECT id, batch_id, patch_id FROM batch_project_patches WHERE batch_id = {batch.id} AND patch_id = {patch.id}")
        )
        row = result.fetchone()
        assert row is not None, f"BatchProjectPatch relationship not found in the database"
        assert row[1] == batch.id, f"Batch ID mismatch: {row[1]} != {batch.id}"
        assert row[2] == patch.id, f"Patch ID mismatch: {row[2]} != {patch.id}"
        logger.info(f"Verified BatchProjectPatch relationship in database: {row}")
    
        # Query the batch using SQLAlchemy ORM
        stmt = select(Batch).where(Batch.id == batch.id)
        result = await async_session.execute(stmt)
        db_batch = result.scalars().first()
        assert db_batch is not None, f"Batch with ID {batch.id} not found using SQLAlchemy ORM"
        assert db_batch.name == batch_name, f"Batch name mismatch: {db_batch.name} != {batch_name}"
        logger.info(f"Verified batch can be queried using SQLAlchemy ORM: {db_batch.name}")
    
        # Query the patch using SQLAlchemy ORM
        stmt = select(ProjectPatch).where(ProjectPatch.id == patch.id)
        result = await async_session.execute(stmt)
        db_patch = result.scalars().first()
        assert db_patch is not None, f"Patch with ID {patch.id} not found using SQLAlchemy ORM"
        assert db_patch.patch == patch_content, f"Patch content mismatch: {db_patch.patch} != {patch_content}"
        logger.info(f"Verified patch can be queried using SQLAlchemy ORM: {db_patch.patch}")
    
        # Query the relationship using SQLAlchemy ORM
        stmt = select(BatchProjectPatch).where(
            (BatchProjectPatch.batch_id == batch.id) & 
            (BatchProjectPatch.patch_id == patch.id)
        )
        result = await async_session.execute(stmt)
        db_batch_patch = result.scalars().first()
        assert db_batch_patch is not None, f"BatchProjectPatch relationship not found using SQLAlchemy ORM"
        assert db_batch_patch.batch_id == batch.id, f"Batch ID mismatch: {db_batch_patch.batch_id} != {batch.id}"
        assert db_batch_patch.patch_id == patch.id, f"Patch ID mismatch: {db_batch_patch.patch_id} != {patch.id}"
        logger.info(f"Verified BatchProjectPatch relationship can be queried using SQLAlchemy ORM")
    
        # The transaction will be rolled back automatically at the end of the test


@pytest.mark.asyncio
async def test_schema_aware_queries(async_session):
    """Test that queries are schema-aware and return the correct data."""
    # Start a transaction for this test
    async with async_session.begin():
        # Ensure we're in the test_schema
        await async_session.execute(text("SET search_path TO test_schema"))
        logger.info("Set search path to test_schema")
    
        # Create a unique identifier for this test run
        unique_id = str(uuid.uuid4())
    
        # Create a test project
        project_name = f"Schema Test Project {unique_id}"
        project = Project(name=project_name, settings={"key": "value"}, enabled=True)
        async_session.add(project)
        await async_session.flush()
        logger.info(f"Created project with ID: {project.id} and name: {project_name}")
    
        # Create a batch associated with the project
        batch_name = f"Schema Test Batch {unique_id}"
        batch = Batch(
            name=batch_name,
            is_active=True,
            is_processed=False,
            project_id=project.id
        )
        async_session.add(batch)
        await async_session.flush()
        logger.info(f"Created batch with ID: {batch.id} and name: {batch_name}")
    
        # Verify the batch was created with the correct name using a direct SQL query
        result = await async_session.execute(
            text(f"SELECT name FROM batches WHERE id = {batch.id}")
        )
        db_batch_name = result.scalar()
        assert db_batch_name == batch_name, f"Batch name mismatch: {db_batch_name} != {batch_name}"
        logger.info(f"Verified batch name in database: {db_batch_name}")
    
        # Query the batch using SQLAlchemy ORM
        stmt = select(Batch).where(Batch.id == batch.id)
        result = await async_session.execute(stmt)
        db_batch = result.scalars().first()
        assert db_batch is not None, f"Batch with ID {batch.id} not found using SQLAlchemy ORM"
        assert db_batch.name == batch_name, f"Batch name mismatch: {db_batch.name} != {batch_name}"
        logger.info(f"Verified batch can be queried using SQLAlchemy ORM: {db_batch.name}")
    
        # Create a second batch with a different name
        batch2_name = f"Schema Test Batch 2 {unique_id}"
        batch2 = Batch(
            name=batch2_name,
            is_active=True,
            is_processed=False,
            project_id=project.id
        )
        async_session.add(batch2)
        await async_session.flush()
        logger.info(f"Created second batch with ID: {batch2.id} and name: {batch2_name}")
    
        # Query all batches for the project
        stmt = select(Batch).where(Batch.project_id == project.id)
        result = await async_session.execute(stmt)
        batches = result.scalars().all()
        assert len(batches) == 2, f"Expected 2 batches, found {len(batches)}"
        batch_names = [b.name for b in batches]
        logger.info(f"Found batches: {batch_names}")
        assert batch_name in batch_names, f"Batch name {batch_name} not found in {batch_names}"
        assert batch2_name in batch_names, f"Batch name {batch2_name} not found in {batch_names}"
        logger.info(f"Verified both batches can be queried using SQLAlchemy ORM")
    
        # The transaction will be rolled back automatically at the end of the test 