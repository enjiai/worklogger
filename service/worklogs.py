import logging
import os
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Tuple

import openai
import pytz as pytz

from api.code_watch.diff_watcher import get_projects
from api.jira.client import get_tasks_in_statuses, Task
from api.metrics.batch_metrics import BatchMetricsCollector
from api.openai.client import OpenAI
from domain.common_db import save_worklog, mark_batches_as_processed, select_non_saved_worklogs
from domain.db.batches import Batches
from domain.worklog import Worklog
from models import SessionLocal, Project, Batch
from settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Working hours configuration
WORKING_HOURS_START = 13  # 9 AM
WORKING_HOURS_END = 22  # 5 PM

# JQL query to retrieve tasks in the specified statuses
# some comment
# Jira REST API endpoint for searching issues

# Initialize OpenAI API
openai.api_key = settings.OPENAI_API_KEY
logger.info("OpenAI API key loaded from settings for worklogs service")

client = openai.OpenAI(
    api_key=settings.OPENAI_API_KEY,
    organization=settings.OPENAI_ORGANIZATION,
    project=settings.OPENAI_PROJECT,
)


@dataclass
class TimeRange:
    start: datetime
    end: datetime
    batch_id: int


def get_daily_metrics_as_tables() -> Tuple[str, str]:
    projects = get_projects()

    overall_metrics_text = f'|{"Project":^25}|{"Added":^15}|{"Removed":^15}|{"Affected":^15}|{"Files":^15}|\n'
    unique_metrics_text = f'|{"Project":^25}|{"Added":^15}|{"Removed":^15}|{"Affected":^15}|{"Files":^15}|\n'

    for project in projects:
        collector = BatchMetricsCollector(project_id=project.id)
        common_metrics, unique_metrics = collector.get_patch_metrics()
        overall_metrics_text += f'|{project.name:>25}|{common_metrics.to_string()}|\n'
        unique_metrics_text += f'|{project.name:>25}|{unique_metrics.to_string()}|\n'

    return overall_metrics_text, unique_metrics_text


# Function to convert diff to text
def diff_to_text(diff):
    diff_text = ""
    for diff_item in diff:
        diff_text += f"diff --git a/{diff_item.a_path} b/{diff_item.b_path}\n"
        diff_text += f"index {diff_item.a_blob.hexsha[:7] if diff_item.a_blob else '0000000'}..{diff_item.b_blob.hexsha[:7] if diff_item.b_blob else '0000000'} {diff_item.change_type}\n"
        if diff_item.diff:
            new_text = diff_item.diff.decode('utf-8')
            if len(new_text) + len(diff_text) > 4096:
                if len(diff_text) > 0:
                    yield diff_text
                    diff_text = ""
                else:
                    yield new_text
            else:
                diff_text += new_text
    yield diff_text


# Function to get commit details
def get_commit_details(commit):
    for diff in diff_to_text(commit.diff(create_patch=True)):
        yield {
            'message': commit.message,
            'diff': diff,
        }


# Function to split time between commits based on complexity
def calculate_time_spent(commits):
    times = []
    total_seconds = 0
    last_commit_time = None

    for i, commit in enumerate(commits):
        commit_time = datetime.fromtimestamp(commit.committed_date)
        if i > 0:
            time_diff = (commit_time - last_commit_time).total_seconds()
            total_seconds += time_diff
            times.append(time_diff)
        last_commit_time = commit_time

    # Normalize times to the total working day duration
    start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = datetime.now().replace(hour=23, minute=59, second=59, microsecond=0)
    working_day_seconds = (end_of_day - start_of_day).total_seconds()

    normalized_times = [time / total_seconds * working_day_seconds for time in times]

    return normalized_times


#
# def work():
#     repo_path = '/home/raistlin/work/enjiai/backend'
#     commits = get_todays_commits(repo_path, datetime(year=2024, month=8, day=4),
#                                  ['kirill.a@maddevs.io', 'morinehtar.qwerty@gmail.com'])
#     times_spent = calculate_time_spent(commits)
#
#     for commit, time_spent in zip(commits, times_spent):
#         for commit_details in get_commit_details(commit):
#             for description in get_diff_description(commit_details['message'], commit_details['diff']):
#                 print(description)
#
#         # Assuming the commit message contains the Jira issue key in the format "PROJECT-123"
#         issue_key = commit_details['message'].split()[0]  # Adjust this based on your commit message format
#
#         commit_time = datetime.fromtimestamp(commit.committed_date)
#         start_time = commit_time if WORKING_HOURS_START <= commit_time.hour < WORKING_HOURS_END else None
#         # if not start_time:
#         #     continue  # Skip commits outside of working hours
#
#         print(f'{times_spent}, {commit_time}')
#         # response = create_jira_worklog(issue_key, description, time_spent, start_time)
#         # if response.status_code == 201:
#         #     print(f"Worklog added to {issue_key}")
#         # else:
#         #     print(f"Failed to add worklog to {issue_key}: {response.status_code} - {response.text}")
#

def get_last_changes(project_id: int):
    session = SessionLocal()

    batches = session.query(Batch).filter(
        Batch.project_id == project_id,
        Batch.is_processed == False,
    ).all()
    patches = []
    for batch in batches:
        for p in batch.project_patches:
            patches.append(p.patch)

    if len(patches) == 0:
        return None, None, None

    period = int(timedelta(hours=1).total_seconds())
    half_life = int(period / 2)

    time_based_patches = {}
    for patch in patches:
        if patch.created_at.day < 2:
            continue

        t = int(patch.created_at.timestamp()) % (24 * 3600)

        key_base = int(t / period) * period

        patch_lines = patch.patch.splitlines(keepends=True)
        if key_base not in time_based_patches:
            time_based_patches[key_base] = []

        time_based_patches[key_base].extend(patch_lines)

    # work_process = {}
    # for i in range(0, 47):
    #     keys = [half_life * i, half_life * (i + 1)]
    #     values = []
    #     for key in keys:
    #         values.extend(time_based_patches.get(key, []))
    #     work_process[keys[0]] = values

    return time_based_patches, patches[0].created_at, batches


def parse_daily_job_reponses(hourly_description: str) -> List[Worklog]:
    result = []
    current_worklog = None

    for line in hourly_description:
        print(f'Response line: {line}')

        line = line.strip(' ')
        if line.startswith('+'):
            if current_worklog is not None:
                result.append(current_worklog)

            task_code = line[1:].strip(' \n')
            current_worklog = Worklog(task_code, '', [])
        elif line.startswith('*'):
            if current_worklog is not None:
                current_worklog.brief = line[1:].strip(' \n*')
        elif line.startswith('-'):
            if current_worklog is not None:
                log_line = line[1:].strip(' \n')
                if log_line != '':
                    current_worklog.logs.append(log_line)
    if current_worklog is not None:
        result.append(current_worklog)
    return result


def merge_worklogs(max_worklog_length: timedelta, _worklogs: List[Worklog]):
    worklogs = deepcopy(_worklogs)
    sorted_worklogs = sorted(worklogs, key=lambda wl: (wl.task_code, wl.time_start))
    current_worklog = worklogs[0]
    result_worklogs = []
    max_seconds = max_worklog_length.total_seconds()
    for i in range(1, len(sorted_worklogs) - 1):
        if current_worklog.task_code == worklogs[i].task_code:
            if current_worklog.time_spent_seconds + worklogs[i].time_spent_seconds <= max_seconds:
                current_worklog.time_spent_seconds += worklogs[i].time_spent_seconds
                current_worklog.logs.extend(worklogs[i].logs)
            else:
                result_worklogs.append(current_worklog)
                current_worklog = worklogs[i]
        else:
            result_worklogs.append(current_worklog)
            current_worklog = worklogs[i]

    result_worklogs.append(current_worklog)
    return result_worklogs


def simplify_worklogs(chat: OpenAI, worklogs: List[Worklog], tasks: Dict[str, Task]):
    for worklog in worklogs:
        if len(worklog.logs) > 0:
            task = None
            if worklog.task_code in tasks:
                task = tasks[worklog.task_code]
            essence = chat.get_worklog_essence_description(worklog, task, {})
            # worklog.logs = []
            print(essence)
            worklog.brief = ''.join(essence)


def get_time_ranges(batch_id: int, maximal_range_seconds: int):
    report = Batches().get_time_report(batch_id)
    if len(report) == 0:
        return None
    result = []

    range_seconds = 0
    range_start = report[0]['start_dt']
    range_end = report[0]['end_dt']

    for row in report:
        if row['real_time_elapsed'] == row['time_elapsed']:
            if range_seconds + row['real_time_elapsed'] <= maximal_range_seconds:
                range_seconds += row['real_time_elapsed']
                range_end = row['end_dt']
            else:
                result.append(
                    TimeRange(range_start.astimezone(timezone.utc),
                              range_end.astimezone(timezone.utc),
                              batch_id)
                )
                range_seconds = row['real_time_elapsed']
                range_start = row['start_dt']
                range_end = row['end_dt']
        else:
            result.append(
                TimeRange(range_start.astimezone(timezone.utc),
                          range_end.astimezone(timezone.utc),
                          batch_id)
            )
            range_seconds = row['real_time_elapsed']
            range_start = row['end_dt'] - timedelta(seconds=row['real_time_elapsed'])
            range_end = row['end_dt']
    result.append(TimeRange(
        range_start.astimezone(timezone.utc),
        range_end.astimezone(timezone.utc),
        batch_id)
    )
    return result


def process_job_unprocessed_batches(max_worklog_length: timedelta = timedelta(hours=2), simplify: bool = True):
    db_batches = Batches()
    projects = get_projects()
    chat = OpenAI()
    result_worklogs = {}

    for project in projects:
        print(f'get last changes for project `{project.name}`')
        batches = db_batches.get_non_processed_batches(project.id)

        if not project.settings.get("task_source", {}).get("enabled", True):
            print('no tasks assigned')
            current_tasks = []
        else:
            print('retrieve tasks')
            current_tasks = get_tasks_in_statuses(project.settings["project_prefix"])

        for batch in batches:
            print(f'get last changes for batch `{project.name}: {batch.id}`')
            ranges = get_time_ranges(batch.id, maximal_range_seconds=int(max_worklog_length.total_seconds()))
            if ranges is None:
                print(f'batch is empty `{project.name}: {batch.id}`')
                mark_batches_as_processed([batch])
                continue
            diffs = {}
            ranges_dict = {}
            for r in ranges:
                diffs[r.start] = []
                patches = db_batches.get_patches_in_range(r.batch_id, r.start, r.end.replace(second=59))
                for patch in patches:
                    diffs[r.start].extend(patch.patch.splitlines())
                    ranges_dict[r.start] = r

            print('get job description')
            if len(current_tasks) > 0:
                result = chat.get_hourly_diff_description(diffs, current_tasks)
            else:
                result = chat.get_hourly_diff_description_and_grouping(diffs)

            tasks = {task.external_id: task for task in current_tasks}
            worklogs_by_tasks = {}
            project_worklogs = []

            for time, description in result.items():
                worklogs = parse_daily_job_reponses(description)
                description_text = '\n'.join(description)
                print(f'{time}\n{description_text}\n')

                worklogs_by_tasks = {}
                for worklog in worklogs:
                    if len(worklog.logs) == 0:
                        continue
                    if worklog.task_code not in worklogs_by_tasks:
                        worklogs_by_tasks[worklog.task_code] = Worklog(
                            brief=worklog.brief,
                            task_code=worklog.task_code,
                            time_start=time,
                            time_spent_seconds=int((ranges_dict[time].end - ranges_dict[time].start).total_seconds()),
                            project_id=project.id,
                            logs=[],
                        )
                        worklogs_by_tasks[worklog.task_code].logs.extend(worklog.logs)
                total_logs = 0
                for task, wl in worklogs_by_tasks.items():
                    total_logs += len(wl.logs)

                current_time = time
                for task, wl in worklogs_by_tasks.items():
                    wl.time_start = current_time
                    wl.time_spent_seconds = int(wl.time_spent_seconds * len(wl.logs) / total_logs)
                    current_time += timedelta(seconds=wl.time_spent_seconds)
                    project_worklogs.append(wl)

            if len(project_worklogs) > 0:
                if project not in result_worklogs:
                    result_worklogs[project] = []
                for worklog in project_worklogs:
                    simplify_worklogs(chat, [worklog], tasks)
                    result_worklogs[project].extend([worklog])

            # for batch in batches:
            db_batches.clear_outputs(batch.id)

            for log in project_worklogs:
                save_worklog(project.id, log)

            mark_batches_as_processed([batch])


def process_daily_job(max_worklog_length: timedelta = timedelta(hours=2), simplify: bool = True):
    projects = get_projects()
    result_worklogs = {}

    chat = OpenAI()
    db_batches = Batches()

    for project in projects:
        print(f'get last changes for project `{project.name}`')
        diffs, dt, batches = get_last_changes(project.id)
        if dt is None and diffs is None:
            print('No work for project')
            continue

        if not project.settings.get("task_source", {}).get("enabled", True):
            print('no tasks assigned')
            current_tasks = []
        else:
            print('retrieve tasks')
            current_tasks = get_tasks_in_statuses(project.settings["project_prefix"])

        print('get job description')
        if len(current_tasks) > 0:
            result = chat.get_hourly_diff_description(diffs, current_tasks)
        else:
            result = chat.get_hourly_diff_description_and_grouping(diffs)

        tasks = {task.external_id: task for task in current_tasks}
        project_worklogs = []

        for time, description in result.items():
            hour = int(time / 3600)
            minute = int((time % 3600) / 60)
            time = f'{hour:02}:{minute:02}'
            worklogs = parse_daily_job_reponses(description)
            description_text = '\n'.join(description)
            print(f'{time}\n{description_text}\n')

            for worklog in worklogs:
                if len(worklog.logs) == 0:
                    continue
                if worklog.task_code not in tasks and len(tasks) > 0:
                    print(f'worklog task {worklog.task_code} is not in task list')
                    continue
                worklog.time_start = dt.replace(hour=hour, minute=minute, second=0)
                worklog.project_id = project.id
                project_worklogs.append(worklog)

        if len(project_worklogs) > 0:
            calculate_spent_time(project_worklogs)
            project_worklogs = merge_worklogs(max_worklog_length, project_worklogs)
            simplify_worklogs(chat, project_worklogs, tasks)
            result_worklogs[project] = project_worklogs

        for batch in batches:
            db_batches.clear_outputs(batch.id)

        for log in project_worklogs:
            save_worklog(project.id, log)

        mark_batches_as_processed(batches)

    return result_worklogs, current_tasks


def calculate_spent_time(worklogs: List[Worklog]):
    logs_by_hours = {}
    utc_timezone = pytz.timezone('UTC')
    for worklog in worklogs:

        if worklog.time_start not in logs_by_hours:
            logs_by_hours[worklog.time_start] = []
        logs_by_hours[worklog.time_start].append(worklog)

    for dt, worklogs in logs_by_hours.items():
        log_entries = []
        for worklog in worklogs:
            log_entries.extend(worklog.logs)

        entry_time = timedelta(hours=1).total_seconds() / len(log_entries)
        for worklog in worklogs:
            worklog.time_spent_seconds = int(len(worklog.logs) * entry_time)

    for dt, worklogs in logs_by_hours.items():
        started_at = dt
        for worklog in worklogs:
            worklog.time_start = started_at
            started_at += timedelta(seconds=worklog.time_spent_seconds)
            worklog.time_start = worklog.time_start.replace(tzinfo=utc_timezone, microsecond=0)


def save_worklogs_from_db():
    projects = get_projects()
    for project in projects:
        if not project.settings.get("task_source", {}).get("enabled", True):
            continue
        worklogs = select_non_saved_worklogs(project.id)
        for worklog in worklogs:
            worklog_content = f'{worklog.summary}:\n\r'
            for log in worklog.details.splitlines():
                worklog_content += f'* {log}\n\r'

            if isinstance(worklog, str):
                print('shit')
            print(f'saving {worklog.task_code} -> {worklog.work_seconds} seconds: \n {worklog_content}')
            # create_jira_worklog(worklog.task_code, worklog.summary, worklog.work_seconds, worklog.work_started_at)
        # mark_worklog_as_saved(worklogs)


def save_worklogs(logs: Dict[Project, List[Worklog]]):
    for project, worklogs in logs.items():
        for worklog in worklogs:
            if isinstance(worklog, str):
                print('shit')
            print(f'saving {worklog.task_code} -> {worklog.brief} ({worklog.time_spent_seconds} seconds)')
            # create_jira_worklog(worklog.task_code, worklog.brief, worklog.time_spent_seconds, worklog.time_start)
