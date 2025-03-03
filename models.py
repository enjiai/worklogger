import datetime
import logging

from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, JSON, DateTime, Boolean, MetaData
from sqlalchemy.orm import relationship, sessionmaker, declarative_base, registry

from settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Use database URL from settings
DATABASE_URL = settings.DATABASE_URL
logger.info(f"Using database: {DATABASE_URL}")

# Create a registry and Base class using the newer API
metadata = MetaData(schema=settings.DB_SCHEMA)  # Use schema from settings
mapper_registry = registry(metadata=metadata)
Base = mapper_registry.generate_base()


class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    settings = Column(JSON, nullable=True)
    enabled = Column(Boolean, nullable=False, server_default="true")

    patches = relationship('ProjectPatch', back_populates='project')
    worklogs = relationship('Worklog', back_populates='project')
    commits = relationship('ProjectCommit', back_populates='project')
    batches = relationship('Batch', back_populates='project')
    references = relationship('ProjectReference', back_populates='project')
    threads = relationship('AssistantThread', back_populates='project')


class ProjectPatch(Base):
    __tablename__ = 'project_patches'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    project_id = Column(Integer, ForeignKey('projects.id', name='fk_project_patches_project'), nullable=False)
    branch_name = Column(String, nullable=False)
    branch_commit = Column(String, nullable=True)
    patch = Column(Text, nullable=False)
    processed = Column(Boolean, nullable=False, default=False)
    metric_collected = Column(Integer, nullable=True)

    project = relationship('Project', back_populates='patches')


class ProjectCommit(Base):
    __tablename__ = 'project_commits'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    committed_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    project_id = Column(Integer, ForeignKey('projects.id', name='fk_project_commits_project'), nullable=False)
    branch_name = Column(String, nullable=False)
    branch_commit = Column(String, nullable=True)
    patch = Column(Text, nullable=False)
    commit_message = Column(Text, nullable=False, default=False)
    metric_collected = Column(Boolean, nullable=True)

    project = relationship('Project', back_populates='commits')


class Worklog(Base):
    __tablename__ = 'worklogs'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    project_id = Column(Integer, ForeignKey('projects.id', name='fk_worklogs_project'), nullable=False)
    task_code = Column(String, nullable=False)
    work_started_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    work_seconds = Column(Integer, nullable=False)
    externally_saved = Column(Boolean, nullable=False, default=False)
    project = relationship('Project', back_populates='worklogs')
    summary = Column(String, nullable=False)
    details = Column(String, nullable=False)


class Batch(Base):
    __tablename__ = 'batches'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    name = Column(String, nullable=True)
    last_patch = Column(String, nullable=True)
    last_branch = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_processed = Column(Boolean, nullable=False, default=False)

    project_id = Column(Integer, ForeignKey('projects.id', name='fk_batches_project'), nullable=False)
    project = relationship('Project', back_populates='batches')

    worklogs = relationship('BatchWorklog', back_populates='batch')
    project_patches = relationship('BatchProjectPatch', back_populates='batch')
    commits = relationship('BatchProjectCommit', back_populates='batch')
    code_metrics = relationship('BatchCodeMetrics', back_populates='batch')


class ProjectReference(Base):
    __tablename__ = 'project_reference'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    gpt_prompt = Column(String, nullable=False)

    project_id = Column(Integer, ForeignKey('projects.id', name='fk_project_reference_project'), nullable=False)
    project = relationship('Project', back_populates='references')


class VirtualOlegDialog(Base):
    __tablename__ = 'virtual_Oleg_dialogs'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    is_active = Column(Boolean, nullable=False, default=True)
    situation = Column(String, nullable=True)
    input_message = Column(String, nullable=True)

    references = relationship('DialogReference', back_populates='dialog')


class DialogReference(Base):
    __tablename__ = 'dialog_reference'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    is_response_to_message = Column(String, nullable=True)
    gpt_sample = Column(String, nullable=False)

    dialog_id = Column(Integer, ForeignKey('virtual_Oleg_dialogs.id', name='fk_dialog_reference_dialog'), nullable=False)
    dialog = relationship('VirtualOlegDialog', back_populates='references')


class BatchWorklog(Base):
    __tablename__ = 'batch_worklogs'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    batch_id = Column(Integer, ForeignKey('batches.id', name='fk_batch_worklogs_batch'), nullable=False)
    batch = relationship('Batch', back_populates='worklogs')

    worklog_id = Column(Integer, ForeignKey('worklogs.id', name='fk_batch_worklogs_worklog'), nullable=False)
    worklog = relationship('Worklog')


class BatchProjectPatch(Base):
    __tablename__ = 'batch_project_patches'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    batch_id = Column(Integer, ForeignKey('batches.id', name='fk_batch_project_patches_batch'), nullable=False)
    batch = relationship('Batch', back_populates='project_patches')

    patch_id = Column(Integer, ForeignKey('project_patches.id', name='fk_batch_project_patches_patch'), nullable=False)
    patch = relationship('ProjectPatch')


class BatchProjectCommit(Base):
    __tablename__ = 'batch_project_commits'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    batch_id = Column(Integer, ForeignKey('batches.id', name='fk_batch_project_commits_batch'), nullable=False)
    batch = relationship('Batch', back_populates='commits')

    commit_id = Column(Integer, ForeignKey('project_commits.id', name='fk_batch_project_commits_commit'), nullable=False)
    commit = relationship('ProjectCommit')


class PatchMetrics(Base):
    __tablename__ = 'patch_metrics'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    patch_id = Column(Integer, ForeignKey('project_patches.id', name='fk_patch_metrics_patch'), nullable=False)
    lines_added = Column(Integer, nullable=False)
    lines_removed = Column(Integer, nullable=False)


class AssistantThread(Base):
    __tablename__ = 'openai_assistant_threads'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    closed_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    last_user_message_at = Column(DateTime(timezone=True), default=datetime.datetime.now)

    project_id = Column(Integer, ForeignKey('projects.id', name='fk_assistant_threads_project'), nullable=False)
    project = relationship('Project', back_populates='threads')

    assistant_type = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    session_id = Column(String, nullable=False)


class BatchCodeMetrics(Base):
    __tablename__ = 'batch_code_metrics_log'
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.datetime.now)
    entity = Column(String, nullable=False)
    is_unique = Column(Boolean, nullable=False)

    batch_id = Column(Integer, ForeignKey('batches.id', name='fk_batch_code_metrics_batch'), nullable=False)
    batch = relationship('Batch', back_populates='code_metrics')

    added_lines = Column(Integer, nullable=False)
    removed_lines = Column(Integer, nullable=False)
    affected_lines = Column(Integer, nullable=False)
    affected_files = Column(Integer, nullable=False)

    delta_added_lines = Column(Integer, nullable=False)
    delta_removed_lines = Column(Integer, nullable=False)
    delta_affected_lines = Column(Integer, nullable=False)
    delta_affected_files = Column(Integer, nullable=False)


# Function to get a schema-aware engine
def get_engine(schema=None):
    """Get a database engine with the specified schema."""
    engine = create_engine(DATABASE_URL)
    if schema:
        # Set the search path to the specified schema
        with engine.connect() as conn:
            conn.execute(f"SET search_path TO {schema}")
    else:
        # Use the default schema from settings
        with engine.connect() as conn:
            conn.execute(f"SET search_path TO {settings.DB_SCHEMA}")
    return engine


# Create the default engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables in the default schema (public)
Base.metadata.create_all(bind=engine)
