import sys
import signal
import datetime
import os
import json
import subprocess

from PySide2.QtGui import QIcon
from PySide2.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QAction, QMessageBox, QErrorMessage
from PySide2.QtCore import QRunnable, QTimer

TXT_EDITOR = "notepad.exe"
TRAY_TOOLTIP = 'Work time logger\n{}'
STOP_MODE = False
MSG_BOX_SHOWED = False
TRAY_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.json")
OVERTIMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overtimes.json")
PROGRAM_NAME = "Work Time Logger"
VERSION = "ver. 0.0.1"


class MessageBox:
    @staticmethod
    def show(text, title="Info", icon=QMessageBox.Information, detailed_text="", informative_text="", buttons=""):
        msg = QMessageBox()

        msg.setText(text)
        msg.setWindowTitle(title)
        msg.setIcon(icon)

        if detailed_text:
            msg.setDetailedText(detailed_text)

        if informative_text:
            msg.setInformativeText(informative_text)

        if buttons:
            msg.setStandardButtons(QMessageBox.Ok)

        msg.exec_()


class JsonHelpers:
    @staticmethod
    def read_file(file_path):
        """
        Read content from specific json file.
        :param json_path: path to json file.
        :return: loaded json content or empty dict.
        """
        try:
            with open(file_path, 'r') as fp:
                return json.load(fp)
        except Exception as exc:
            MessageBox.show(
                text=str(exc),
                title="Error",
                icon=QMessageBox.Critical,
                detailed_text=str(type(exc))
            )
            JsonHelpers.write_file(file_path, {})
            return {}

    @staticmethod
    def write_file(file_path, data):
        """
        Write specific data into json file.

        :param file_path: path to file where data will be written.
        :param data: data to write into file
        :return: None.
        """
        try:
            with open(file_path, 'w') as fp:
                json.dump(data, fp, indent=3)
        except Exception as exc:
            MessageBox.show(
                text=str(exc),
                title="Error",
                icon=QMessageBox.Critical,
                detailed_text=str(type(exc))
            )


class Worker(QRunnable):
    def __init__(self, time, update_tooltip_text):
        super(Worker, self).__init__()
        self.time = time
        self.update_tooltip_text = update_tooltip_text


class Time:
    def __init__(self):
        self.reference_time = datetime.timedelta(minutes=0, hours=8)
        self.now_date = ""
        self.time_left = ""

    def log_time(self, first_run=False, msg_box=True):
        now = datetime.datetime.now()
        self.now_date = str(now.strftime("%Y/%m/%d"))
        now_time = str(now.strftime("%H:%M:%S"))

        self._write_time_to_file(now_time, first_run)

        msg = "Logged time:\n\n{} {}".format(self.now_date, now_time)

        if msg_box:
            MessageBox.show(text=msg)

    def _check_date_exist(self, data):
        if self.now_date in data.keys():
            return True

        return False

    def _write_time_to_file(self, now_time, first_run):
        data = JsonHelpers.read_file(FILE_PATH)
        self.log_label = "Log break"

        if self._check_date_exist(data):
            if data[self.now_date]:
                if data[self.now_date][-1]["END"]:
                    data[self.now_date].append({"START": now_time, "END": ""})
                else:
                    if not first_run:
                        data[self.now_date][-1]["END"] = now_time
                        self.log_label = "Log work"
            else:
                data[self.now_date] = list()
                data[self.now_date].append({"START": now_time, "END": ""})
        else:
            data[self.now_date] = list()
            data[self.now_date].append({"START": now_time, "END": ""})

        JsonHelpers.write_file(FILE_PATH, data)

    def get_today_logs(self):
        msg = "Not logged any time!"

        data = JsonHelpers.read_file(FILE_PATH)
        date_exists = self._check_date_exist(data)

        if date_exists:
            msg = ""
            for elements in data[self.now_date]:
                for element_name, element_value in elements.items():
                    msg = "{}{}:{}\n".format(msg, element_name, element_value)

        MessageBox.show(text=msg)

    def show_working_time(self, silent_mode=False):
        working_time = self._calculate_working_time()
        msg = "Summary working time:\n\nWorking time: {}\n".format(working_time)
        overtime = False

        delta = self._calculate_time_left(working_time, self.reference_time)
        end_time = datetime.datetime.now() + delta

        end_time = end_time.strftime("%H:%M:%S")

        if working_time > self.reference_time:
            delta = working_time - self.reference_time
            overtime = True

        if working_time:
            if not overtime:
                msg = "{}Time left: {}\nEstimated end work: {}\n".format(msg, delta, end_time)
                self.time_left = "Time left: {}".format(delta)
            elif overtime:
                msg = "{}Overtimes: {}".format(msg, delta)
                self.time_left = "Overtimes: {}".format(delta)
        if not silent_mode:
            MessageBox.show(text=msg)

    def _calculate_time_left(self, working_time=None, reference_time=None):
        if not (working_time and reference_time):
            working_time = self._calculate_working_time()
            reference_time = datetime.timedelta(minutes=0, hours=8)

        to_go = reference_time - working_time

        return to_go

    def _calculate_working_time(self):
        working_time = datetime.timedelta()
        data = JsonHelpers.read_file(FILE_PATH)

        if self._check_date_exist(data):
            for elements in data[self.now_date]:
                if elements["END"]:
                    end = datetime.datetime.strptime(elements["END"], '%H:%M:%S')
                    start = datetime.datetime.strptime(elements["START"], '%H:%M:%S')
                    delta = end - start
                else:
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    current_time = datetime.datetime.strptime(now, '%H:%M:%S')
                    start = datetime.datetime.strptime(elements["START"], '%H:%M:%S')
                    delta = current_time - start

                working_time += delta
        else:
            msg = "Not found start time in current day."
            MessageBox.show(text=msg)
            global MSG_BOX_SHOWED
            MSG_BOX_SHOWED = False
            self.log_time(msg_box=False)

        return working_time

    def show_overtimes(self):
        now = datetime.datetime.now()
        month = str(now.strftime("%Y/%m"))
        msg = ""

        data = JsonHelpers.read_file(OVERTIMES_PATH)
        for date in data.keys():
            if month in date:
                msg = "{}{}: {}\n".format(msg, date, data[date])

        if msg:
            msg = "Overtimes in: '{}'\n\n{}".format(month, msg)
        else:
            msg = "No overtimes in current month."

        MessageBox.show(text=msg)

    def _edit_times(self, file_path):
        try:
            subprocess.run([TXT_EDITOR, file_path])
        except Exception as exc:
            wx.MessageBox(str(exc), "Error", wx.OK | wx.ICON_ERROR)

        self.show_working_time(silent_mode=True)

    def edit_logs(self):
        self._edit_times(FILE_PATH)

    def edit_overtimes(self):
        self._edit_times(OVERTIMES_PATH)


class App:
    def __init__(self):
        self.app = QApplication([])
        self.app.setQuitOnLastWindowClosed(False)

        self.time = Time()
        self.time.log_time(msg_box=False, first_run=True)

        self.tray = self._prepare_tray_menu()
        self._update_tooltip_text()
        self.tray.show()

        self.timer = self._prepare_overtime_check_timer()
        self.timer.start()

    def _prepare_tray_menu(self):
        tray = QSystemTrayIcon(QIcon("icon.png"), self.app)
        menu = QMenu()

        menu = self._set_tray_menu_item(menu, "Log break", self._log_time)
        menu = self._set_tray_menu_item(menu, "Working time", self._show_working_time)

        menu.addSeparator()

        menu = self._set_tray_menu_item(menu, "Show logs", self._get_today_log)
        menu = self._set_tray_menu_item(menu, "Show overtimes", self._show_overtimes)

        menu.addSeparator()

        menu = self._set_tray_menu_item(menu, "Edit logs", self._edit_logs)
        menu = self._set_tray_menu_item(menu, "Edit overtimes", self._edit_overtimes)

        menu.addSeparator()

        menu = self._set_tray_menu_item(menu, "About", self._show_about_message)
        menu = self._set_tray_menu_item(menu, "Exit", self.app.exit)

        tray.setContextMenu(menu)
        tray.setToolTip("Work time logger")

        return tray

    def _prepare_overtime_check_timer(self):
        self._check_overtime()

        timer = QTimer()
        timer.setInterval(60 * 1000)
        timer.timeout.connect(self._check_overtime)

        return timer

    def _log_time(self, first_run=False):
        self.time.log_time(first_run=first_run)
        self._update_tooltip_text()
        self._change_log_work_break()

    def _get_today_log(self):
        self.time.get_today_logs()
        self._update_tooltip_text()

    def _show_working_time(self):
        self.time.show_working_time()
        self._update_tooltip_text()

    def _show_overtimes(self):
        self.time.show_overtimes()
        self._update_tooltip_text()

    def _edit_logs(self):
        self.time.edit_logs()
        self._update_tooltip_text()

    def _edit_overtimes(self):
        self.time.edit_overtimes()
        self._show_tray_message("LOL")
        self._update_tooltip_text()

    def _update_tooltip_text(self):
        self.time.show_working_time(silent_mode=True)
        self.tray.setToolTip(TRAY_TOOLTIP.format(self.time.time_left))

    def _set_tray_menu_item(self, menu, name, method):
        menu_item = menu.addAction(name)
        menu_item.triggered.connect(method)

        return menu

    def _change_log_work_break(self):
        for action in self.tray.contextMenu().actions():
            if action.text() == "Log break":
                action.setText("Log work")

                return True
            elif action.text() == "Log work":
                action.setText("Log break")

                return True

        return False

    def _show_tray_message(self, title, text):
        self.tray.showMessage(title, text)

    def _not_implemented_yet_msg(self):
        MessageBox.show(text="Not implemented yet!", title="ERROR", icon=QMessageBox.Critical)

    def _show_about_message(self):
        msg = "{} {}".format(PROGRAM_NAME, VERSION)
        MessageBox.show(text=msg, title="About")

    def run(self):
        self._show_tray_message("Work Time Logger", "Application started.")
        status = self.app.exec_()
        self.time.log_time()

        sys.exit(status)

    def _check_overtime(self):
        global MSG_BOX_SHOWED
        working_time = self.time._calculate_working_time()

        if working_time > self.time.reference_time:
            if not MSG_BOX_SHOWED:
                msg = "It's time to end your work.\n\n{}".format(working_time)
                self._show_tray_message(text=msg)
                MSG_BOX_SHOWED = True
            overtimes = working_time - self.time.reference_time

            self._save_overtimes(overtimes)
        self._update_tooltip_text()

    def _save_overtimes(self, overtimes):
        now = datetime.datetime.now()
        now_date = str(now.strftime("%Y/%m/%d"))

        data = JsonHelpers.read_file(OVERTIMES_PATH)
        data[now_date] = str(overtimes)
        JsonHelpers.write_file(OVERTIMES_PATH, data)

        data = JsonHelpers.read_file(FILE_PATH)
        data[now_date][-1]["END"] = str(datetime.datetime.now().strftime("%H:%M:%S"))
        JsonHelpers.write_file(FILE_PATH, data)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = App()
    app.run()
