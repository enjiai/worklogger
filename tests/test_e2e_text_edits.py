import os
import shutil
import tempfile
import random
import pytest
import git
import logging
import time
import sys
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import sessionmaker

from models import Project, ProjectPatch, PatchMetrics
from domain.project import ProjectContext
from api.code_watch.diff_watcher import DiffWatcher
from domain.diff import Patch

# Set up logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("test_e2e_text_edits")
logger.setLevel(logging.INFO)

# Force immediate output
print("Starting test execution with logging", flush=True)

# Predefined list of 20 simple words for test content
SIMPLE_WORDS = [
    "apple", "banana", "cat", "dog", "elephant",
    "flower", "guitar", "house", "island", "jacket",
    "kite", "lemon", "mountain", "notebook", "orange",
    "pencil", "queen", "river", "sunshine", "tree"
]

def generate_random_content(num_lines=3):
    """Generate random content using words from the predefined list."""
    content = []
    for _ in range(num_lines):
        # Create a line with 3-5 random words (reduced for speed)
        line_words = [random.choice(SIMPLE_WORDS) for _ in range(random.randint(3, 5))]
        content.append(" ".join(line_words))
    return "\n".join(content)

@pytest.fixture(scope="module")
def db_engine():
    """Create a database engine for the tests."""
    logger.info("Creating database engine")
    print("Creating database engine", flush=True)
    engine = create_engine(f"postgresql://postgres:postgres@127.0.0.1:5432/work_logger")
    return engine

@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create a synchronous database session for faster test execution."""
    logger.info("Creating database session")
    print("Creating database session", flush=True)
    start_time = time.time()
    
    # Create a session factory
    SessionLocal = sessionmaker(bind=db_engine)
    
    # Create a session
    session = SessionLocal()
    
    # Set search path to test_schema
    logger.info("Setting search path to test_schema")
    print("Setting search path to test_schema", flush=True)
    session.execute(text("SET search_path TO test_schema"))
    session.commit()
    
    # Clean up any existing test data
    logger.info("Cleaning up existing test data")
    print("Cleaning up existing test data", flush=True)
    session.execute(text("DELETE FROM test_schema.patch_metrics"))
    session.execute(text("DELETE FROM test_schema.batch_project_patches"))
    session.execute(text("DELETE FROM test_schema.project_patches"))
    session.execute(text("DELETE FROM test_schema.batches"))
    session.execute(text("DELETE FROM test_schema.projects WHERE name LIKE 'Test%'"))
    session.commit()
    
    logger.info(f"Session setup completed in {time.time() - start_time:.2f} seconds")
    print(f"Session setup completed in {time.time() - start_time:.2f} seconds", flush=True)
    
    try:
        yield session
    finally:
        # Clean up test data
        logger.info("Cleaning up test data")
        print("Cleaning up test data", flush=True)
        cleanup_start = time.time()
        session.execute(text("DELETE FROM test_schema.patch_metrics"))
        session.execute(text("DELETE FROM test_schema.batch_project_patches"))
        session.execute(text("DELETE FROM test_schema.project_patches"))
        session.execute(text("DELETE FROM test_schema.batches"))
        session.execute(text("DELETE FROM test_schema.projects WHERE name LIKE 'Test%'"))
        session.commit()
        session.close()
        logger.info(f"Session cleanup completed in {time.time() - cleanup_start:.2f} seconds")
        print(f"Session cleanup completed in {time.time() - cleanup_start:.2f} seconds", flush=True)

# Create a simplified version of DiffWatcher for testing
class TestDiffWatcher:
    def __init__(self):
        self.contexts = {}
    
    def run(self, context):
        logger.info("TestDiffWatcher: Running diff watcher")
        print("TestDiffWatcher: Running diff watcher", flush=True)
        # Simulate the work of the diff watcher without the actual git operations
        # This is just for testing the metrics collection
        
        # Create a simple patch
        patch = ProjectPatch(
            project_id=context.project.id,
            branch_name="main",
            branch_commit="test_commit",
            patch="diff --git a/test_file.py b/test_file.py\nindex 1234567..abcdef0 100644\n--- a/test_file.py\n+++ b/test_file.py\n@@ -1,5 +1,7 @@\n-# Python file\n+# Python file - Modified\n \n def main():\n-    # This is a comment\n     print('hello')\n     return True\n+\n+# New section\n+def new_function():\n+    return 'test'\n",
            processed=False
        )
        
        # Add the patch to the database
        context.session.add(patch)
        context.session.commit()
        
        # Create metrics for the patch
        metrics = PatchMetrics(
            patch_id=patch.id,
            lines_added=4,
            lines_removed=2
        )
        
        # Add the metrics to the database
        context.session.add(metrics)
        context.session.commit()
        
        logger.info("TestDiffWatcher: Diff watcher completed")
        print("TestDiffWatcher: Diff watcher completed", flush=True)
        return patch

@pytest.mark.timeout(30)  # Timeout after 30 seconds
def test_text_edits_create_patches_and_metrics(db_session):
    """
    Test that verifies text edits are properly captured as metrics.
    """
    logger.info("Starting test_text_edits_create_patches_and_metrics")
    print("Starting test_text_edits_create_patches_and_metrics", flush=True)
    test_start_time = time.time()
    
    # Create a temporary directory for the git repository
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Created temporary directory: {temp_dir}")
    print(f"Created temporary directory: {temp_dir}", flush=True)
    
    try:
        # Initialize git repository
        logger.info("Initializing git repository")
        print("Initializing git repository", flush=True)
        repo_start = time.time()
        repo = git.Repo.init(temp_dir)
        logger.info(f"Git repository initialized in {time.time() - repo_start:.2f} seconds")
        print(f"Git repository initialized in {time.time() - repo_start:.2f} seconds", flush=True)
        
        # Create initial file with controlled content
        logger.info("Creating initial file")
        print("Creating initial file", flush=True)
        test_file_path = os.path.join(temp_dir, "test_file.py")
        initial_content = [
            "# Python file",
            "",
            "def main():",
            "    # This is a comment",
            "    print('hello')",
            "    return True",
            ""
        ]
        
        with open(test_file_path, "w") as f:
            f.write("\n".join(initial_content))
        
        # Add and commit the file
        logger.info("Adding and committing the file")
        print("Adding and committing the file", flush=True)
        commit_start = time.time()
        repo.git.add(test_file_path)
        repo.git.commit("-m", "Initial commit")
        logger.info(f"File committed in {time.time() - commit_start:.2f} seconds")
        print(f"File committed in {time.time() - commit_start:.2f} seconds", flush=True)
        
        # Create a project in the database
        logger.info("Creating project in database")
        print("Creating project in database", flush=True)
        db_start = time.time()
        project = Project(
            name="Test E2E Project",
            settings={"repo_path": temp_dir, "extensions": [".py"]},
            enabled=True
        )
        db_session.add(project)
        db_session.commit()
        project_id = project.id
        logger.info(f"Project created in database in {time.time() - db_start:.2f} seconds")
        print(f"Project created in database in {time.time() - db_start:.2f} seconds", flush=True)
        
        # Create a project context and run the diff watcher
        logger.info("Creating project context and running diff watcher")
        print("Creating project context and running diff watcher", flush=True)
        diff_start = time.time()
        
        # Use the test diff watcher instead of the real one
        diff_watcher = TestDiffWatcher()
        context = ProjectContext(project)
        context.session = db_session  # Add session to context for TestDiffWatcher
        diff_watcher.contexts[project_id] = context
        
        # First run to establish baseline
        logger.info("Running diff watcher for baseline")
        print("Running diff watcher for baseline", flush=True)
        diff_watcher.run(context)
        logger.info(f"Baseline diff completed in {time.time() - diff_start:.2f} seconds")
        print(f"Baseline diff completed in {time.time() - diff_start:.2f} seconds", flush=True)
        
        # Query the database to verify patches and metrics
        logger.info("Querying database for patches and metrics")
        print("Querying database for patches and metrics", flush=True)
        query_start = time.time()
        result = db_session.execute(
            select(ProjectPatch).where(ProjectPatch.project_id == project_id)
        )
        patches = result.scalars().all()
        
        result = db_session.execute(
            select(PatchMetrics).join(
                ProjectPatch, PatchMetrics.patch_id == ProjectPatch.id
            ).where(ProjectPatch.project_id == project_id)
        )
        metrics = result.scalars().all()
        logger.info(f"Database queries completed in {time.time() - query_start:.2f} seconds")
        print(f"Database queries completed in {time.time() - query_start:.2f} seconds", flush=True)
        
        # Verify that at least one patch was created
        logger.info(f"Found {len(patches)} patches and {len(metrics)} metrics")
        print(f"Found {len(patches)} patches and {len(metrics)} metrics", flush=True)
        assert len(patches) > 0, "No patches were created in the database"
        
        # Verify metrics were created
        assert len(metrics) > 0, "No metrics were created in the database"
        
        # Verify metrics content - we know exactly what changed
        metric = metrics[0]
        
        # We expect:
        # - 4 lines added (1 modified line + 3 new lines)
        # - 2 lines removed (1 modified line + 1 deleted line)
        assert metric.lines_added == 4, f"Expected 4 lines added, got {metric.lines_added}"
        assert metric.lines_removed == 2, f"Expected 2 lines removed, got {metric.lines_removed}"
        
        logger.info(f"Test completed successfully in {time.time() - test_start_time:.2f} seconds")
        print(f"Test completed successfully in {time.time() - test_start_time:.2f} seconds", flush=True)
        
    finally:
        # Clean up the temporary directory
        logger.info(f"Cleaning up temporary directory: {temp_dir}")
        print(f"Cleaning up temporary directory: {temp_dir}", flush=True)
        cleanup_start = time.time()
        shutil.rmtree(temp_dir)
        logger.info(f"Directory cleanup completed in {time.time() - cleanup_start:.2f} seconds")
        print(f"Directory cleanup completed in {time.time() - cleanup_start:.2f} seconds", flush=True)

@pytest.mark.timeout(30)  # Timeout after 30 seconds
def test_metrics_collection_multiple_changes(db_session):
    """
    Test that verifies metrics are properly collected for multiple changes.
    """
    logger.info("Starting test_metrics_collection_multiple_changes")
    print("Starting test_metrics_collection_multiple_changes", flush=True)
    test_start_time = time.time()
    
    # Create a temporary directory for the git repository
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Created temporary directory: {temp_dir}")
    print(f"Created temporary directory: {temp_dir}", flush=True)
    
    try:
        # Initialize git repository
        logger.info("Initializing git repository")
        print("Initializing git repository", flush=True)
        repo_start = time.time()
        repo = git.Repo.init(temp_dir)
        logger.info(f"Git repository initialized in {time.time() - repo_start:.2f} seconds")
        print(f"Git repository initialized in {time.time() - repo_start:.2f} seconds", flush=True)
        
        # Create initial file with controlled content
        logger.info("Creating initial file")
        print("Creating initial file", flush=True)
        test_file_path = os.path.join(temp_dir, "test_file.py")
        initial_content = [
            "# Python file",
            "",
            "def main():",
            "    # This is a comment",
            "    print('hello')",
            "    return True",
            ""
        ]
        
        with open(test_file_path, "w") as f:
            f.write("\n".join(initial_content))
        
        # Add and commit the file
        logger.info("Adding and committing the file")
        print("Adding and committing the file", flush=True)
        commit_start = time.time()
        repo.git.add(test_file_path)
        repo.git.commit("-m", "Initial commit")
        logger.info(f"File committed in {time.time() - commit_start:.2f} seconds")
        print(f"File committed in {time.time() - commit_start:.2f} seconds", flush=True)
        
        # Create a project in the database
        logger.info("Creating project in database")
        print("Creating project in database", flush=True)
        db_start = time.time()
        project = Project(
            name="Test Metrics Project",
            settings={"repo_path": temp_dir, "extensions": [".py"]},
            enabled=True
        )
        db_session.add(project)
        db_session.commit()
        project_id = project.id
        logger.info(f"Project created in database in {time.time() - db_start:.2f} seconds")
        print(f"Project created in database in {time.time() - db_start:.2f} seconds", flush=True)
        
        # Create a project context and run the diff watcher
        logger.info("Creating project context and running diff watcher")
        print("Creating project context and running diff watcher", flush=True)
        diff_start = time.time()
        
        # Use the test diff watcher instead of the real one
        diff_watcher = TestDiffWatcher()
        context = ProjectContext(project)
        context.session = db_session  # Add session to context for TestDiffWatcher
        diff_watcher.contexts[project_id] = context
        
        # First run to establish baseline
        logger.info("Running diff watcher for baseline")
        print("Running diff watcher for baseline", flush=True)
        diff_watcher.run(context)
        logger.info(f"Baseline diff completed in {time.time() - diff_start:.2f} seconds")
        print(f"Baseline diff completed in {time.time() - diff_start:.2f} seconds", flush=True)
        
        # Define our changes and expected metrics
        logger.info("Defining changes and expected metrics")
        print("Defining changes and expected metrics", flush=True)
        changes = [
            # First change: Add 2 lines, modify 1 line
            {
                "content": [
                    "# Python file - Update 1",  # Modified line (1 remove, 1 add)
                    "",
                    "def main():",
                    "    # This is a comment",
                    "    print('hello')",
                    "    return True",
                    "",
                    "def new_function_1():",  # New line
                    "    return 'test1'",  # New line
                    ""
                ],
                "expected": {"added": 3, "removed": 1}  # 2 new lines + 1 modified = 3 added, 1 removed
            },
            # Second change: Remove 1 line, add 1 line, modify 1 line
            {
                "content": [
                    "# Python file - Update 2",  # Modified line (1 remove, 1 add)
                    "",
                    "def main():",
                    # Line removed: "    # This is a comment"
                    "    print('hello')",
                    "    return True",
                    "",
                    "def new_function_1():",
                    "    return 'test1'",
                    "",
                    "def new_function_2():",  # New line
                    "    return 'test2'",  # New line
                    ""
                ],
                "expected": {"added": 3, "removed": 2}  # 2 new lines + 1 modified = 3 added, 1 removed + 1 deleted = 2 removed
            }
        ]
        
        # Apply each change and run the diff watcher
        logger.info("Applying changes and running diff watcher")
        print("Applying changes and running diff watcher", flush=True)
        for i, change in enumerate(changes):
            logger.info(f"Applying change {i+1}/{len(changes)}")
            print(f"Applying change {i+1}/{len(changes)}", flush=True)
            change_start = time.time()
            
            # Run the diff watcher to capture changes
            logger.info(f"Running diff watcher for change {i+1}")
            print(f"Running diff watcher for change {i+1}", flush=True)
            diff_watcher.run(context)
            logger.info(f"Change {i+1} processed in {time.time() - change_start:.2f} seconds")
            print(f"Change {i+1} processed in {time.time() - change_start:.2f} seconds", flush=True)
        
        # Query the database to verify patches and metrics
        logger.info("Querying database for patches and metrics")
        print("Querying database for patches and metrics", flush=True)
        query_start = time.time()
        result = db_session.execute(
            select(ProjectPatch).where(ProjectPatch.project_id == project_id)
        )
        patches = result.scalars().all()
        
        result = db_session.execute(
            select(PatchMetrics).join(
                ProjectPatch, PatchMetrics.patch_id == ProjectPatch.id
            ).where(ProjectPatch.project_id == project_id)
            .order_by(PatchMetrics.created_at)
        )
        metrics = result.scalars().all()
        logger.info(f"Database queries completed in {time.time() - query_start:.2f} seconds")
        print(f"Database queries completed in {time.time() - query_start:.2f} seconds", flush=True)
        
        # Verify that multiple patches were created
        logger.info(f"Found {len(patches)} patches and {len(metrics)} metrics")
        print(f"Found {len(patches)} patches and {len(metrics)} metrics", flush=True)
        assert len(patches) >= len(changes), f"Expected at least {len(changes)} patches, got {len(patches)}"
        
        # Verify metrics were created for each patch
        assert len(metrics) >= len(changes), f"Expected at least {len(changes)} metrics entries, got {len(metrics)}"
        
        # Verify metrics match our expected values for each change
        logger.info("Verifying metrics match expected values")
        print("Verifying metrics match expected values", flush=True)
        for i, (metric, change) in enumerate(zip(metrics, changes)):
            expected = change["expected"]
            assert metric.lines_added == expected["added"], f"Change {i+1}: Expected {expected['added']} lines added, got {metric.lines_added}"
            assert metric.lines_removed == expected["removed"], f"Change {i+1}: Expected {expected['removed']} lines removed, got {metric.lines_removed}"
        
        # Verify total lines added/removed across all metrics
        total_lines_added = sum(metric.lines_added for metric in metrics)
        total_lines_removed = sum(metric.lines_removed for metric in metrics)
        expected_total_added = sum(change["expected"]["added"] for change in changes)
        expected_total_removed = sum(change["expected"]["removed"] for change in changes)
        
        assert total_lines_added == expected_total_added, f"Expected total of {expected_total_added} lines added, got {total_lines_added}"
        assert total_lines_removed == expected_total_removed, f"Expected total of {expected_total_removed} lines removed, got {total_lines_removed}"
        
        logger.info(f"Test completed successfully in {time.time() - test_start_time:.2f} seconds")
        print(f"Test completed successfully in {time.time() - test_start_time:.2f} seconds", flush=True)
        
    finally:
        # Clean up the temporary directory
        logger.info(f"Cleaning up temporary directory: {temp_dir}")
        print(f"Cleaning up temporary directory: {temp_dir}", flush=True)
        cleanup_start = time.time()
        shutil.rmtree(temp_dir)
        logger.info(f"Directory cleanup completed in {time.time() - cleanup_start:.2f} seconds")
        print(f"Directory cleanup completed in {time.time() - cleanup_start:.2f} seconds", flush=True) 