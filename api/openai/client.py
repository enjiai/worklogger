import logging
import os
from typing import Dict

import openai

from domain.worklog import Worklog
from settings import settings

# Configure logging
logger = logging.getLogger(__name__)

# Use OpenAI API key from settings
OPENAI_API_KEY = settings.OPENAI_API_KEY
logger.info("OpenAI API key loaded from settings")

Oleg_description = ('''
You are Олег. Олег is a high-efficient manager who created its own custom software solutions company.
You are former software developer and devops who knows well most popular programming languages and frameworks for the
You are aware of his own productivity, and also his employees productivity.
You are very good at process management and his motto in process management is 'Fix the process, not human'.
You doesn't like when processes are violated
You've read a lot of books. Among them 
* `Tibetan book of the dead`
* `Portrait of Dorian Gray` by Oscar Wilde
* `The Kama Sutra of Public Speaking` by Gandapas, Radislav
* `The god delusion` by Richard Dawkins
* `Principles` by Ray Dahlio
* `Capital` by Karl Marx
* `Practical Management Philosophy` by Konosuke Matsushita
* `The Heart of Management` by Konosuke Matsushita
* `Fooled by randomness` by Nassim Taleb
* `Do No Harm: Stories of Life, Death and Brain Surgery` by Henry Marsh
* `Rhetorics` by Aristotle
* `Politics` by Aristotle
* `Radically human` by Daugherty Wilson
* `The Phoenix Project` by Gene Kim, Kevin Behr and George Spafford
* `Creators take control` by Edward Lee
* `On task` by Badre
* `Endure` by Cameron Hanes
* `Business model Generation` by Wiley publishing house
* `Power and prediction` by Aggrawal, Gans and Goldfarb 
* `How Asia works` by Joe Studwell
* `Discipline equals freedom` by Jocko Willink
* `The surprising power of liberating structures` by Lipmanowicz and McCandless
Our work process consists of several various processes:
Task management, daily routines, and the coding itself.

Task must have consistent name, description and estimation in hours:
Tasks:
Tasks usually have the following statuses: todo, in progress, in review, testing, done.
You must check a quality of task description. Is it fully understandable? Is the estimation made properly?
Daily routines:
We must start our day with writing a standup message. Ensure that worklog was written
Coding process:
You use metrics of a work process
If there is no any work for a long time (> 1 hour), this is suspicious
If there are no new commits (> 3 hours), this will lead to possible job loss
If quality of job is low, this makes you angry
If there are no tests where they are needed, you make the human to write tests

Your personality:
You are swift-brained and sarcastic erudite. You usually use black humour in your explanations. 
You explain complex things in a very simple language full of proper analogies. 
You use an emotional pressure if some work process is violated, or a lie is detected, or the human is unsure.
You are strongly result-oriented person who understands that well-working process is a result also.
You use russian language possibly with swearing lexicon and sarcasm. 

How do You work:
Initially I give you a trouble that person has and you need to try to fix it
 
''')


class OpenAI:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=OPENAI_API_KEY,
            organization='org-5BSIHvHSUBcynZRbeEb8JlA3',
            project='proj_ZtYgjcThjp1ulUrMZUKukn5n',
        )

    def ask(self, system_text, content_text):
        try:
            stream = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": system_text,
                    }, {
                        "role": "user",
                        "content": content_text,
                    }
                ],
                max_tokens=250,
                stream=True,
            )
            txt = ""
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    c = chunk.choices[0].delta.content
                    if c == '\n' or c.endswith('\n'):
                        yield txt
                        txt = ''
                    else:
                        txt += c
            if txt != '':
                yield txt
        except Exception as e:
            print(f"Error calling OpenAI API: {e}")
            return "Could not generate description"

    def get_commit_description(self, commit_message, commit_diff, additional_references: Dict[str, str]):
        system_text = "You are a helpful assistant that provides descriptions for purpose of git commits. "
        "You must briefly, essentially and consistently explain what was implemented in each diff in one short sentence "
        "for each 100 lines of changes of each changed file separately. Every explanation must come on a separate line."
        "If the files were deleted or moved, try to understand purpose of such a files according to path and names."
        "Do not say `this/the/that commit`, just explain what was done."
        "Rearrange lines to groups with similar purpose and related jobs inside it. "
        "Do not nest groups. "
        "Before each group purpose with add a line with possible time spent for this group startimg from words 'Time spent:' without any other prefixes and followed by amount of minutes. "
        "After such a time must follow group overall jobs description line starting from * sign. After such a group description must follow job descriptions each on separate line and starting from - sign."

        request = f"Repository Context:\n"
        f'Commit Message: {commit_message}\n'
        f"Diff: {commit_diff}\n"
        f"Describe what was done in this commit according to commit message"

        response = list(self.ask(system_text, request))
        return response

    def get_hourly_diff_description(self, diffs, tasks, additional_references: Dict[str, str] = {}):
        system_text = (
            "You are a helpful assistant that provides descriptions for purpose of git commits. "
            "You must briefly, essentially and consistently explain what was implemented in each diff in one short sentence "
            "for each 100 lines of changes of each changed file separately. Every explanation must come on a separate line."
            "Take into consideration names of the files to understand context better"
            "If the files were deleted or moved, try to understand purpose of such a files according to path and names."
            "Prefer describing changes in logic of program rather than refactoring."
            "Do not say `this/the/that commit`, just explain what was done."
            "Refer to previous hour job chapter to ensure that job description is consistent with previously performed job"
            "Rearrange lines to job groups with similar purpose and related jobs inside it. Classify each group to one of available tasks."
            "Do not nest groups. Do not use blocks formatting like ``` (three apostrophes). Every line must start only from one of the following symbols: `*`, `+`, `-`"
            "Each job group description line starting from + sign. After such a + must come assigned task code. After this task code must be newline symbol"
            "After task code there must be a description of job done in the group on a separate line starting from *. After this group description must be newline symbol"
            "After such a group description must follow job descriptions each on separate line and starting from - sign."
        )
        if len(additional_references) > 0:
            reference_text = 'Take into consideration the following information about the project as an additional context'
            references = '\n'.join([f'`{name}: {ref}`' for name, ref in additional_references.items()])
            system_text = f'{system_text}\n{reference_text}:\n{references}\n'
        responses = {}
        previous_period_description = 'None job was done'
        task_list = ''
        for task in tasks:
            task_list += f'Task code: {task.external_id}\n\tBrief:{task.brief}\n\tDescription: {task.description}\n'
        for time in sorted(diffs.keys()):
            diff = diffs[time]
            if len(diff) == 0:
                continue

            request = (
                f"Repository Context:\n"
                f"Previous hour job:\n```{previous_period_description}```\n"
                f"Diffs: \n```{''.join(diff)}```\n"
                f'Available tasks: ```{task_list}```\n'
                f"Describe what was done in this diffs taking into consideration "
            )
            response = list(self.ask(system_text, request))
            responses[time] = response
            previous_period_description = '\n'.join(response)
        return responses

    def get_hourly_diff_description_and_grouping(self, diffs, additional_references=None):
        if additional_references is None:
            additional_references = {}
        system_text = (
            "You are a helpful assistant that provides descriptions for purpose of git commits. "
            "You must briefly, essentially and consistently explain what was implemented in each diff in one short sentence "
            "for each 100 lines of changes of each changed file separately. Every explanation must come on a separate line."
            "Take into consideration names of the files to understand context better"
            "If the files were deleted or moved, try to understand purpose of such a files according to path and names."
            "Prefer describing changes in logic of program rather than refactoring."
            "Do not say `this/the/that commit`, just explain what was done."
            "Refer to previous hour job chapter to ensure that job description is consistent with previously performed job"
            "Rearrange lines to job groups with similar purpose and related jobs inside it. Classify each group to one of available tasks."
            "Do not nest groups. Do not use blocks formatting like ``` (three apostrophes). Every line must start only from one of the following symbols: `*`, `+`, `-`"
            "Each job group description line starting from + sign. After such a + must come number by order starting from one. After this number there must be newline symbol"
            "After order number there must be a description of job done in the group on a separate line starting from *. After this group description must be newline symbol"
            "After such a group description must follow job descriptions each on separate line and starting from - sign."
        )
        if len(additional_references) > 0:
            reference_text = 'Take into consideration the following information about the project as an additional context'
            references = '\n'.join([f'`{name}: {ref}`' for name, ref in additional_references.items()])
            system_text = f'{system_text}\n{reference_text}:\n{references}\n'
        responses = {}
        previous_period_description = 'None job was done'
        for time in sorted(diffs.keys()):
            diff = diffs[time]
            if len(diff) == 0:
                continue

            request = (
                f"Repository Context:\n"
                f"Previous hour job:\n```{previous_period_description}```\n"
                f"Diffs: \n```{''.join(diff)}```\n"
                f"Describe what was done in this diffs taking into consideration "
            )
            response = list(self.ask(system_text, request))
            responses[time] = response
            previous_period_description = '\n'.join(response)
        return responses

    def get_worklog_essence_description(self, worklog: Worklog, task, additional_references: Dict[str, str]):
        system_text = (
            "You are a helpful assistant that provides descriptions for purpose of work logs. "
            "You take log entries as step-by-step job description. "
            "You take the task and log brief as a context for the following procedure:"
            "You must briefly, essentially and consistently compile all the log entries into one to three sentences, "
            "describing what was done in the whole logged process. "
            "Prefer describing changes in logic of program rather than refactoring."
            "You must use manager-friendly live language also understandable for newbie developer."
            "Do not say `this/the/that task, commit, file`, just explain what was done from the first face."
            "The response must contain only brief, essential and consistent log entries compilation"
            "Translate text into Russian except abbreviations, class names and file names."
        )
        if task is not None:
            task_context = f'Task code: {task.external_id}\n\tBrief:{task.brief}\n\tDescription: {task.description}\n'
        else:
            task_context = 'No task context, just simplify the logs'
        request = (
            f"Context:\n"
            f'Task: ```{task_context}```\n'
            f'Log brief: ```{worklog.brief}```\n'
            f'Log entries: ```{worklog.logs}```\n'
            f"Describe what was done in this diffs taking into consideration "
        )
        response = list(self.ask(system_text, request))
        return response
