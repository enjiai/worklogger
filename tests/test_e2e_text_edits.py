import os
import shutil
import tempfile
import pytest
import asyncio
import git
from datetime import datetime
from sqlalchemy import select, text

from models import Project, ProjectPatch, PatchMetrics, Batch, BatchProjectPatch
from domain.project import ProjectContext
from api.code_watch.diff_watcher import DiffWatcher
from settings import settings


@pytest.mark.asyncio
async def test_text_edits_create_patches_and_metrics(async_session):
    """
    End-to-end test that verifies text edits in a git repository are properly
    captured in the database as patches and metrics.
    
    This test follows the project rules:
    - Uses a real database with test_schema
    - Creates a temporary git repository
    - Creates a project in the database through business logic
    - Makes file changes in the repository
    - Verifies results by querying the database
    
    Note: We use a 5-second check period for faster testing, while the
    production system uses the configured DIFF_CHECK_PERIOD_SECONDS (default 60).
    """
    # Create a temporary directory for the git repository
    temp_dir = tempfile.mkdtemp()
    try:
        # Set a shorter check period for testing
        original_check_period = settings.DIFF_CHECK_PERIOD_SECONDS
        settings.DIFF_CHECK_PERIOD_SECONDS = 5
        
        # Initialize git repository
        repo = git.Repo.init(temp_dir)
        
        # Create initial file
        test_file_path = os.path.join(temp_dir, "test_file.py")
        with open(test_file_path, "w") as f:
            f.write("# Initial content\n\ndef hello_world():\n    print('Hello, World!')\n")
        
        # Add and commit the file
        repo.git.add(test_file_path)
        repo.git.commit("-m", "Initial commit")
        
        # Create a project in the database
        async with async_session.begin():
            # Set search path to test_schema
            await async_session.execute(text("SET search_path TO test_schema"))
            
            # Create project through business logic
            project = Project(
                name="Test E2E Project",
                settings={"repo_path": temp_dir, "extensions": [".py"]},
                enabled=True
            )
            async_session.add(project)
            await async_session.flush()
            project_id = project.id
            
            # Create an active batch for the project (normally done by Batches.get_active_batch)
            batch = Batch(
                name="Test Batch",
                is_active=True,
                project_id=project_id,
                created_at=datetime.now()
            )
            async_session.add(batch)
            await async_session.flush()
            batch_id = batch.id
        
        # Create a project context and run the diff watcher once
        diff_watcher = DiffWatcher()
        
        # First run to establish baseline
        context = ProjectContext(project)
        diff_watcher.contexts[project_id] = context
        diff_watcher.run(context)
        
        # Modify the file with specific changes we can verify
        with open(test_file_path, "w") as f:
            f.write("# Modified content\n\ndef hello_world():\n    print('Hello, Modified World!')\n\ndef new_function():\n    return 42\n")
        
        # Run the diff watcher again to capture changes
        diff_watcher.run(context)
        
        # Wait a moment for async operations to complete
        await asyncio.sleep(1)
        
        # Query the database to verify patches were created
        async with async_session.begin():
            # Set search path to test_schema
            await async_session.execute(text("SET search_path TO test_schema"))
            
            # Query for patches
            result = await async_session.execute(
                select(ProjectPatch).where(ProjectPatch.project_id == project_id)
            )
            patches = result.scalars().all()
            
            # Query for metrics
            result = await async_session.execute(
                select(PatchMetrics).join(
                    ProjectPatch, PatchMetrics.patch_id == ProjectPatch.id
                ).where(ProjectPatch.project_id == project_id)
            )
            metrics = result.scalars().all()
            
            # Query for batch-patch relationships
            result = await async_session.execute(
                select(BatchProjectPatch)
                .where(BatchProjectPatch.batch_id == batch_id)
            )
            batch_patches = result.scalars().all()
        
        # Verify that at least one patch was created
        assert len(patches) > 0, "No patches were created in the database"
        
        # Verify patch content
        patch = patches[0]
        assert "Modified" in patch.patch, "Patch does not contain the modified content"
        assert "new_function" in patch.patch, "Patch does not contain the new function"
        assert patch.branch_name == context.current_branch, "Branch name not correctly recorded"
        assert patch.branch_commit == context.current_commit, "Commit hash not correctly recorded"
        
        # Verify metrics were created
        assert len(metrics) > 0, "No metrics were created in the database"
        
        # Verify metrics content - we know exactly what changed
        metric = metrics[0]
        assert metric.lines_added >= 3, f"Expected at least 3 lines added, got {metric.lines_added}"
        assert metric.lines_removed >= 1, f"Expected at least 1 line removed, got {metric.lines_removed}"
        assert metric.patch_id == patch.id, "Metric is not linked to the correct patch"
        
        # Verify batch-patch relationship
        assert len(batch_patches) > 0, "Patch was not associated with a batch"
        assert batch_patches[0].patch_id == patch.id, "Batch is not linked to the correct patch"
        
    finally:
        # Restore original check period
        settings.DIFF_CHECK_PERIOD_SECONDS = original_check_period
        
        # Clean up the temporary directory
        shutil.rmtree(temp_dir) 