import datetime
import logging
from typing import Tuple, List

from sqlalchemy import or_

from domain.db.batches import Batches
from domain.diff import Patch
from domain.project import ProjectContext, ProjectCommit
from domain.worklog import Worklog
from models import SessionLocal, Project, ProjectPatch, PatchMetrics, Worklog as DBWorklog, ProjectCommit as DBCommit, \
    AssistantThread, Batch
from settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Create database session
session = SessionLocal()
logger.info(f"Database session created using {settings.DATABASE_URL}")

PatchMetricsVersion = 2


def get_projects():
    projects = session.query(Project).filter(Project.enabled == True).all()
    return projects


def save_patch_metrics_to_db(patch_id: int):
    print(f"Saving metrics of {patch_id}")
    db_patch = session.query(ProjectPatch).filter(ProjectPatch.id == patch_id).one_or_none()
    if db_patch is None:
        print("Patch is not found")
        return

    patch = Patch(db_patch.patch)
    metrics = patch.get_metrics()

    patch_metrics = session.query(PatchMetrics).filter(PatchMetrics.patch_id == patch_id).one_or_none()
    if patch_metrics is None:
        patch_metrics = PatchMetrics(
            created_at=db_patch.created_at,
            patch_id=db_patch.id,
            lines_added=metrics['lines']['added'],
            lines_removed=metrics['lines']['removed'],
        )
        db_patch.metric_collected = PatchMetricsVersion
        session.add(patch_metrics)
    else:
        patch_metrics.created_at = db_patch.created_at
        patch_metrics.patch_id = db_patch.id
        patch_metrics.lines_added = metrics['lines']['added']
        patch_metrics.lines_removed = metrics['lines']['removed']

    session.commit()


def save_diff_to_db(context: ProjectContext, essential_diff: str, whole_diff: str) -> ProjectPatch:
    print("Saving diff")
    patch = ProjectPatch(
        project_id=context.project.id,
        branch_name=context.current_branch,
        branch_commit=context.current_commit,
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        patch=essential_diff
    )
    session.add(patch)
    session.commit()

    save_patch_metrics_to_db(patch.id)
    batches = Batches()

    batch = batches.get_active_batch(context.project.id)
    batches.add_patch(batch.id, patch.id)

    return patch


def save_worklog(project_id: int, worklog: Worklog) -> Worklog:
    print("Saving worklog")
    worklog = DBWorklog(
        project_id=project_id,
        task_code=worklog.task_code,
        work_started_at=worklog.time_start,
        work_seconds=worklog.time_spent_seconds,
        externally_saved=False,
        summary=worklog.brief,
        details='\n'.join(worklog.logs),
    )
    session.add(worklog)
    session.commit()

    batches = Batches()

    batch = batches.get_active_batch(project_id)
    batches.add_worklog(batch.id, worklog.id)

    # save_patch_metrics_to_db(worklog.id)
    return worklog


def get_commit(commit_hex_hash: str) -> DBCommit:
    return session.query(DBCommit).filter(DBCommit.branch_commit == commit_hex_hash).one_or_none()


def save_commit(project_id: int, commit: ProjectCommit) -> Tuple[DBCommit, bool]:
    existing_commit = session.query(DBCommit).filter(DBCommit.branch_commit == commit.hex_hash).one_or_none()
    if existing_commit is not None:
        return existing_commit, False

    db_commit = DBCommit(
        project_id=project_id,
        created_at=datetime.datetime.now(),
        committed_at=commit.created_at,
        branch_name=commit.branch,
        branch_commit=commit.hex_hash,
        patch=commit.diff,
        commit_message=commit.description,
        metric_collected=False,
    )
    session.add(db_commit)
    session.commit()

    batches = Batches()

    batch = batches.get_active_batch(project_id)
    batches.add_commit(batch.id, db_commit.id)

    # save_patch_metrics_to_db(worklog.id)
    return db_commit, True


def update_missing_metrics():
    db_patches = session.query(ProjectPatch).filter(or_(
        ProjectPatch.metric_collected != PatchMetricsVersion,
        ProjectPatch.metric_collected == None,
    )).all()
    for patch in db_patches:
        save_patch_metrics_to_db(patch.id)


def get_openai_session_by_id(session_id: str) -> AssistantThread | None:
    return session.query(AssistantThread).filter(
        AssistantThread.session_id == session_id,
    ).one_or_none()


def get_openai_session(project_id, assistant_type: str) -> AssistantThread:
    return session.query(AssistantThread).filter(
        AssistantThread.project_id == project_id,
        AssistantThread.assistant_type == assistant_type,
        AssistantThread.closed_at == None,
    ).one_or_none()


def update_openai_session(session_id: str) -> AssistantThread | None:
    thread = get_openai_session_by_id(session_id)
    if thread is None:
        return None
    thread.last_user_message_at = datetime.datetime.now(tz=datetime.timezone.utc)
    session.commit()
    return thread


def close_openai_session(session_id: str) -> bool:
    thread = get_openai_session_by_id(session_id)
    if thread is None:
        return False
    thread.closed_at = datetime.datetime.now(tz=datetime.timezone.utc)
    session.commit()
    return True


def create_openai_session(project_id, assistant_type, session_id: str, reason: str) -> AssistantThread:
    thread = AssistantThread(
        created_at=datetime.datetime.now(tz=datetime.timezone.utc),
        project_id=project_id,
        assistant_type=assistant_type,
        session_id=session_id,
        reason=reason,
    )
    session.add(thread)
    session.commit()
    return thread


def mark_batches_as_processed(batches: List[Batch]) -> bool:
    for batch in batches:
        batch.is_processed = True
    session.commit()
    return True


def select_non_saved_worklogs(project_id: int):
    return session.query(DBWorklog).filter(
        DBWorklog.project_id == project_id,
        DBWorklog.externally_saved == False
    ).all()


def mark_worklog_as_saved(worklogs: List[DBWorklog]):
    for worklog in worklogs:
        worklog.externally_saved = True
    session.commit()
