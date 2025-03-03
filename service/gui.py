import asyncio
import datetime
import sys

from PyQt5.QtCore import QPoint, QTimer
from PyQt5.QtGui import QIcon
# import asyncpg
from PyQt5.QtWidgets import QSystemTrayIcon, QMenu, QAction, QDialog, QLabel, QVBoxLayout
from qasync import asyncSlot

from api.code_watch.diff_watcher import DiffWatcher
from api.commit_watch.commit_watcher import CommitWatcher
from api.openai import client
from domain.common_db import update_missing_metrics
from service import worklogs
from service.worklogs import get_daily_metrics_as_tables, save_worklogs_from_db
from settings import settings


class KDEAssistant:
    def __init__(self, app):
        self.diff_watchers = DiffWatcher()
        self.commit_watcher = CommitWatcher()
        self.openai = client.OpenAI()
        self.current_tasks = []
        self.last_worklogs = {}
        self.overall_metrics = ""
        self.unique_metrics = ""

        self.app = app
        self.tray_icon = QSystemTrayIcon(self.get_icon('user-available-symbolic.svg'), self.app)

        # self.dialog = self.create_dialog()

        # self.loop = loop
        # self.loop.create_task(self.check_db_value())

    async def arun(self):
        menu = QMenu()

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.setToolTip("Lazy Bitch KDE assistant")

        exit_action = QAction("Exit", self.app)
        exit_action.triggered.connect(lambda checked: self.exit())

        daily_job_action = QAction("Process daily job", self.app)
        daily_job_action.triggered.connect(lambda checked: self.process_daily_job())

        process_commits_action = QAction("Process commits", self.app)
        process_commits_action.triggered.connect(lambda checked: self.process_commits())

        save_job_action = QAction("Save daily job", self.app)
        save_job_action.triggered.connect(lambda checked: self.save_daily_job())

        menu.addAction(process_commits_action)
        menu.addAction(save_job_action)
        menu.addAction(daily_job_action)
        menu.addAction(exit_action)

        await self.process_everything()

        self.timer = QTimer()
        self.timer.timeout.connect(lambda: self.process_everything())
        self.timer.start(settings.DIFF_CHECK_PERIOD_SECONDS * 1000)  # Use configurable check period

        update_missing_metrics()
        self.print_daily_metrics()
        self.tray_icon.show()

    def get_icon(self, icon_name):
        return QIcon(f'./icons/{icon_name}')

    @asyncSlot()
    async def process_commits(self):
        self.commit_watcher.start_once()

    @asyncSlot()
    async def process_daily_job(self):
        worklogs.process_job_unprocessed_batches()
        print("Processing is done!!!")

    @asyncSlot()
    async def save_daily_job(self):
        # save_worklogs(self.last_worklogs)
        save_worklogs_from_db()

    @asyncSlot()
    async def process_everything(self):
        self.diff_watchers.start_once()
        if datetime.datetime.now().minute % 5 == 0:
            self.commit_watcher.start_once()

    def print_daily_metrics(self):
        overall, unique = get_daily_metrics_as_tables()
        if self.overall_metrics != overall:
            print(f'|{"Overall metrics":-^105}|\n{overall}\n')
            self.overall_metrics = overall
        if self.unique_metrics != unique:
            print(f'|{"Unique metrics":-^105}|\n{unique}\n')
            self.unique_metrics = unique

    def create_dialog(self):
        dialog = QDialog()
        dialog.setWindowTitle("Dialog Near Tray")
        layout = QVBoxLayout()
        label = QLabel("This is a dialog near the tray icon.")
        layout.addWidget(label)
        dialog.setLayout(layout)
        dialog.resize(200, 100)
        return dialog

    def show_dialog(self):
        screen_geometry = self.app.primaryScreen().geometry()
        tray_geometry = self.tray_icon.geometry()
        tray_position = tray_geometry.topLeft()

        dialog_x = tray_position.x()
        dialog_y = tray_position.y() - self.dialog.height()

        if dialog_y < 0:
            dialog_y = tray_position.y() + tray_geometry.height()

        self.dialog.move(QPoint(dialog_x, dialog_y))
        self.dialog.show()

    async def check_db_value(self):
        # conn = await asyncpg.connect(user='user', password='password', database='database', host='127.0.0.1')
        while True:
            # result = await conn.fetchrow('SELECT your_column FROM your_table LIMIT 1')
            # if result:
            #     value = result['your_column']
            #     if value == 'some_condition':
            #         self.tray_icon.setIcon(QIcon('path/to/icon1.png'))
            #     elif value == 'another_condition':
            #         self.tray_icon.setIcon(QIcon('path/to/icon2.png'))
            #     else:
            #         self.tray_icon.setIcon(QIcon('path/to/default.png'))
            await asyncio.sleep(5)

    @asyncSlot()
    async def exit(self):
        self.app.quit()

    async def run(self):
        print("Assistant is starting")
        sys.exit(self.app.exec_())


async def run():
    print('Starting processing your work, lazy bitch')
    assistant = KDEAssistant()
    assistant.run()


if __name__ == '__main__':
    asyncio.run(run())
