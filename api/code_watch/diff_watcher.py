import asyncio
import datetime
import difflib
import os
from typing import Dict, List

from domain.common_db import get_projects, save_diff_to_db
from domain.db.batches import Batches
from domain.diff import Patch
from domain.project import ProjectContext
from settings import settings


class DiffWatcher:
    def __init__(self):
        self.contexts: Dict[int, ProjectContext] = {}

    def load_file_content(self, file_path):
        if not os.path.exists(file_path):
            return ""
        with open(file_path, 'r') as file:
            return file.read()

    def texts_diff(self, text1, text2, name1, name2):
        diff = difflib.unified_diff(
            text1.splitlines(keepends=True),
            text2.splitlines(keepends=True),
            fromfile=name1,
            tofile=name2,
            lineterm=''
        )
        return list(diff)

    def filter_files_by_extension(self, patch: Patch, extensions: List[str]):
        diffs = patch.get_diffs()
        filtered_diffs = {}
        for file_path, diff in diffs.items():
            for extension in extensions:
                if file_path.endswith(extension):
                    filtered_diffs[file_path] = diff
        return

    def fix_lineends(self, lines: List[str]):
        for n in range(len(lines)):
            line = lines[n].rstrip('\r\n \t')
            line += "\n"
            lines[n] = line
        return lines

    def generate_intermediate_patch(self, first_diff_content, current_diff_content, repo_path, extensions: List[str]):
        first_diffs = Patch(first_diff_content.splitlines(keepends=True)).get_diffs()
        current_patch = Patch(current_diff_content.splitlines(keepends=True))
        last_diffs = current_patch.get_diffs()

        intermediate_patches = []
        filenames = []

        # Process each file mentioned in the diffs
        for file_path in first_diffs.keys() | last_diffs.keys():
            for extension in extensions:
                if file_path.endswith(extension):
                    filenames.append(file_path)
                    break

        for file_path in filenames:
            abs_file_path = os.path.join(repo_path, file_path)
            initial_content = []
            current_content = []
            reversed_content = []
            initial_content = []
            file_content = []
            first_file = []

            if file_path in first_diffs and first_diffs[file_path].is_deleted:
                initial_content = []
            else:
                file_content = self.load_file_content(abs_file_path).splitlines(keepends=True)  # nice
                if file_path in last_diffs:
                    reversed_content = last_diffs[file_path].revert(file_content)
                    if file_path in first_diffs:
                        initial_content = first_diffs[file_path].apply(reversed_content)  # bad

            first_file = (
                initial_content if len(initial_content) > 0
                else reversed_content
                if len(reversed_content) > 0
                else file_content
            )

            if file_path not in first_diffs and file_path in last_diffs and len(reversed_content) == 0:
                first_file = []

            if file_path in last_diffs:
                if not last_diffs[file_path].is_deleted:
                    current_content = self.load_file_content(abs_file_path).splitlines(keepends=True)  # nice
                else:
                    current_content = []

            if first_file == current_content:
                continue

            self.fix_lineends(first_file)
            self.fix_lineends(current_content)

            intermediate_patch = difflib.unified_diff(
                first_file,  # .splitlines(keepends=True),
                current_content,  # .splitlines(keepends=True),
                fromfile=file_path,
                tofile=file_path,
                lineterm=''
            )
            intermediate_patches.extend(intermediate_patch)

        for i in range(len(intermediate_patches)):
            intermediate_patches[i] = intermediate_patches[i].strip("\r\n\t")

        return '\n'.join(intermediate_patches), len(intermediate_patches), \
            current_patch.get_files_with_extensions_only(extensions)

    # Function to get the current diff of the repository
    def get_current_diff(self, repo, extensions: List[str]):
        diff = self.get_tracked_files_diff(repo)
        new_files_patches = self.get_untracked_files_diff(extensions, repo)
        if new_files_patches != '':
            diff += f'\n{new_files_patches}'

        if not diff.endswith('\n'):
            diff += '\n'

        return diff

    def get_tracked_files_diff(self, repo):
        return repo.git.diff('HEAD', full_index=True, unified=3)

    def get_untracked_files_diff(self, extensions, repo):
        untracked_files = repo.untracked_files
        filenames = set[str]()
        for untracked_file in untracked_files:
            for extension in extensions:
                if untracked_file.endswith(extension):
                    filenames.add(untracked_file)
        new_files_patches = ""
        for filename in filenames:
            a_name = "a/dev/null"
            b_name = f'b/{filename}'

            file_content = self.load_file_content(f'{repo.working_tree_dir}/{filename}')
            lines = file_content.strip('\r\n\t ').splitlines(keepends=True)
            if len(lines) > 0:
                new_files_patches += f'diff --git {a_name} {b_name}\n'
                new_files_patches += f"--- {a_name}\n+++ {b_name}\n"
                new_files_patches += f"@@ -0,0 +0,{len(lines)} @@\n"
                for line in lines:
                    new_files_patches += f'+{line}'.strip("\r\n") + '\n'
        return new_files_patches

    def start_once(self):
        projects = get_projects()
        for project in projects:
            if project.id not in self.contexts:
                self.contexts[project.id] = ProjectContext(project)
            context = self.contexts[project.id]

            if context.repo.head.commit.hexsha != context.current_commit:
                context.current_branch = context.repo.active_branch.name
                context.current_commit = context.repo.head.commit.hexsha
                context.last_diff = None
            self.run(context)

    async def start(self):
        while True:
            self.start_once()
            # Calculate sleep time to align with the start of the next period
            current_second = datetime.datetime.now().second
            sleep_time = settings.DIFF_CHECK_PERIOD_SECONDS - current_second % settings.DIFF_CHECK_PERIOD_SECONDS
            await asyncio.sleep(sleep_time)
            # await asyncio.sleep(2)

    def run(self, context: ProjectContext):
        if context.last_diff is None:
            current_diff, branch = Batches().get_current_patch(context.project.id)
            if current_diff != '' and branch == context.current_branch:
                context.last_diff = current_diff
                print(
                    f'Initial diff is read from database for {context.project.name}/{context.current_branch}/{context.current_commit}')
            else:
                context.last_diff = self.get_current_diff(context.repo, context.extensions)
                print(
                    f'Initial diff is read from filesystem for {context.project.name}/{context.current_branch}/{context.current_commit}')
                return

        current_diff = self.get_current_diff(context.repo, context.extensions)
        current_diff = Patch(current_diff).get_files_with_extensions_only(context.extensions).to_string()

        if current_diff.strip("\r\n\t ") == context.last_diff.strip("\r\n\t "):
            # print("No difference found")
            return
        print(f"{context.project.name}: diffs are not equal")
        intermediate_patch, size, full_current_diff = self.generate_intermediate_patch(context.last_diff,
                                                                                       current_diff,
                                                                                       context.repo_path,
                                                                                       context.extensions)

        if intermediate_patch != "":
            print(f"{context.project.name}: diff is built ({size} lines) and being saved")
            save_diff_to_db(context, intermediate_patch, "")
            patch = Patch(intermediate_patch)
            print(f"Metrics of saved diff: {patch.get_metrics()}")
            context.last_diff = current_diff
            Batches().update_current_patch(context.project.id, full_current_diff.to_string(), context.current_branch)
        else:
            print(f"{context.project.name}: diff is empty, looks like it contains files out of our filters")

            # diff = self.texts_diff(context.last_diff, current_diff, 'prev.diff', 'current.diff')
            # if diff != '':
            #     diff_strings = ''.join(diff)
            #     print(f'diff of diffs:\n{diff_strings}\n')

            if context.last_diff is None:
                context.last_diff = current_diff
