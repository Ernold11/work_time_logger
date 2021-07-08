import sys
import signal
import datetime
import os
import json
import subprocess
import psutil
import win32process

from win32gui import GetForegroundWindow
from pynput import keyboard, mouse
from PySide2.QtGui import QIcon, QFont
from PySide2.QtWidgets import QSystemTrayIcon, QMenu, QApplication, QAction, QMessageBox, QErrorMessage
from PySide2.QtCore import QRunnable, QTimer

TXT_EDITOR = "notepad.exe"
TRAY_TOOLTIP = 'Work time logger\n{}'
STOP_MODE = False
MSG_BOX_SHOWED = False
TRAY_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.json")
OVERTIMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overtimes.json")
ACTIVITY_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "activity_logs.json")
PROGRAM_NAME = "Work Time Logger"
VERSION = "ver. 0.0.1"


class MessageBox:
    @staticmethod
    def show(text, title="Info", icon=QMessageBox.Information, detailed_text="", informative_text="", buttons=""):
        msg = QMessageBox()

        msg.setText(text)
        msg.setWindowTitle(title)
        msg.setIcon(icon)
        msg.setFont(QFont('Consolas', 9))

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
            if (exc.__class__ == IOError):
                JsonHelpers.write_file(file_path, {})
            else:
                MessageBox.show(
                    text="Work Time Logger will open incorrect file.\nPlease validate data, make necessary changes, save and start application again.",
                    title="Error",
                    icon=QMessageBox.Critical
                )
                try:
                    subprocess.run([TXT_EDITOR, file_path])
                except Exception as exc:
                    MessageBox.show(
                        text=str(exc),
                        title="Error",
                        icon=QMessageBox.Critical,
                        detailed_text=str(type(exc))
                    )
                
                sys.exit(1)
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


class ActivityLogger:
    def __init__(self):
        now = datetime.datetime.now()
        self.now_date = str(now.strftime("%Y/%m/%d"))
        self.keyboard_listener = self._set_keyboard_listener()
        self.keyboard_listener.start()

        self.mouse_listener = self._set_mouse_listener()
        self.mouse_listener.start()

        self.process_time = JsonHelpers.read_file(ACTIVITY_LOG_PATH)
        self.activity_detected = False

        self.counter = 0

    def _set_keyboard_listener(self):
        listener = keyboard.Listener(
            on_press=self._set_activity,
            on_release=self._set_activity
        )

        return listener

    def _set_mouse_listener(self):
        listener = mouse.Listener(
            on_move=self._set_activity,
            on_click=self._set_activity,
            on_scroll=self._set_activity
        )

        return listener

    def _set_activity(self, *args, **kwargs):
        self.activity_detected = True

    def _detect_current_application(self):
        try:
            now = datetime.datetime.now()
            self.now_date = str(now.strftime("%Y/%m/%d"))
            current_app = psutil.Process(
                win32process.GetWindowThreadProcessId(GetForegroundWindow())[1]).name().replace(
                ".exe", "")

            if self.now_date not in self.process_time.keys():
                self.process_time[self.now_date] = {}

            if current_app not in self.process_time[self.now_date].keys():
                self.process_time[self.now_date][current_app] = {"active": 0, "inactive": 0}

            if self.activity_detected:
                self.process_time[self.now_date][current_app]["active"] = \
                    self.process_time[self.now_date][current_app]["active"] + 1
            else:
                self.process_time[self.now_date][current_app]["inactive"] = \
                    self.process_time[self.now_date][current_app]["inactive"] + 1
        except Exception as exc:
            if (exc.__class__ != psutil.NoSuchProcess) and ("pid" not in str(exc)):
                MessageBox.show(
                    text=str(exc),
                    title="Error",
                    icon=QMessageBox.Critical,
                    detailed_text=str(type(exc))
                )

        self._calculate_summary_time()

        self.activity_detected = False

    def _calculate_summary_time(self):
        summary = {"active": 0, "inactive": 0}

        self.process_time[self.now_date].pop("Summary", None)

        for time in self.process_time[self.now_date].values():
            summary["active"] += time["active"]
            summary["inactive"] += time["inactive"]

        self.process_time[self.now_date]["Summary"] = summary

    def show_activity(self):
        msg = "Application usage:\n"
        self._calculate_summary_time()
        data = self.process_time[self.now_date]

        sorted_keys = sorted(data, key=lambda x: (data[x]['active']), reverse=True)

        for key in sorted_keys:
            converted_active = str(datetime.timedelta(seconds=data[key]["active"]))
            converted_inactive = str(datetime.timedelta(seconds=data[key]["inactive"]))
            if key != "Summary":
                msg = "{}\n{:<20}\tactive: {:<6}\tinactive: {}".format(msg, key, converted_active, converted_inactive)

        converted_active = str(datetime.timedelta(seconds=data["Summary"]["active"]))
        converted_inactive = str(datetime.timedelta(seconds=data["Summary"]["inactive"]))
        msg = "{}\n\n{:<20}\tactive: {:<6}\tinactive: {}".format(msg, "Summary", converted_active, converted_inactive)

        MessageBox.show(text=msg)
        JsonHelpers.write_file(ACTIVITY_LOG_PATH, self.process_time)

    def run(self):
        self.counter = 0

        self._detect_current_application()
        self.counter += 1

        if not self.counter % 60:
            JsonHelpers.write_file(ACTIVITY_LOG_PATH, self.process_time)
            self.counter = 0


class Time:
    def __init__(self):
        self.reference_time = datetime.timedelta(minutes=0, hours=8)
        self.now_date = ""
        self.time_left = ""
        self.is_overtime = False
        self.working_time = JsonHelpers.read_file(FILE_PATH)
        self.overtimes = JsonHelpers.read_file(OVERTIMES_PATH)

    def log_time(self, first_run=False, msg_box=True, exit=False):
        now = datetime.datetime.now()
        self.now_date = str(now.strftime("%Y/%m/%d"))
        now_time = str(now.strftime("%H:%M:%S"))

        self._write_time_to_file(now_time, first_run, exit)

        msg = "Logged time:\n\n{} {}".format(self.now_date, now_time)

        if msg_box:
            MessageBox.show(text=msg)

    def _check_date_exist(self, data):
        if self.now_date in data.keys():
            return True

        return False

    def _write_time_to_file(self, now_time, first_run, exit):
        self.log_label = "Log break"

        if self._check_date_exist(self.working_time):
            if self.working_time[self.now_date]:
                if self.working_time[self.now_date][-1]["END"]:
                    if not exit:
                        self.working_time[self.now_date].append({"START": now_time, "END": ""})
                else:
                    if not first_run:
                        self.working_time[self.now_date][-1]["END"] = now_time
                        self.log_label = "Log work"
            else:
                self.working_time[self.now_date] = list()
                self.working_time[self.now_date].append({"START": now_time, "END": ""})
        else:
            self.working_time[self.now_date] = list()
            self.working_time[self.now_date].append({"START": now_time, "END": ""})

        JsonHelpers.write_file(FILE_PATH, self.working_time)

    def get_today_logs(self):
        msg = "Not logged any time!"

        date_exists = self._check_date_exist(self.working_time)

        if date_exists:
            msg = ""
            for elements in self.working_time[self.now_date]:
                for element_name, element_value in elements.items():
                    msg = "{}{}:{}\n".format(msg, element_name, element_value)

        MessageBox.show(text=msg)

    def show_working_time(self, silent_mode=False):
        working_time = self._calculate_working_time()
        msg = "Today:\n\n{:<20} {}\n".format("Working time:", working_time)
        self.is_overtime = False

        delta = self._calculate_time_left(working_time, self.reference_time)
        end_time = datetime.datetime.now() + delta

        end_time = end_time.strftime("%H:%M:%S")

        if working_time > self.reference_time:
            delta = working_time - self.reference_time
            self.is_overtime = True

        if working_time:
            if not self.is_overtime:
                msg = "{}{:<20} {}\n{:<20} {}\n".format(msg, "Time left:", delta, "Estimated end work:", end_time)
                self.time_left = "Time left: {}".format(delta)
            elif self.is_overtime:
                msg = "{}{:<20} {}".format(msg, "Overtimes:", delta)
                self.time_left = "Overtimes: {}".format(delta)

        month_working_time = self._calculate_summary_working_time()
        msg = "{}\nCurrent month:\n\n{:<20} {}\n".format(msg, "Working time:", month_working_time)

        if not silent_mode:
            MessageBox.show(text=msg)

    def _calculate_summary_working_time(self):
        now = datetime.datetime.now()
        month = "{}/".format(now.strftime("%Y/%m"))
        working_time = datetime.timedelta()

        current_month_days = [day for day in self.working_time.keys() if month in day]

        for day in current_month_days:
            for elements in self.working_time[day]:
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

        working_time = self._convert_timedelta(working_time)

        return working_time

    def _convert_timedelta(self, duration):
        days, seconds = duration.days, duration.seconds
        hours = days * 24 + seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = (seconds % 60)

        return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)

    def _calculate_time_left(self, working_time=None, reference_time=None):
        if not (working_time and reference_time):
            working_time = self._calculate_working_time()
            reference_time = datetime.timedelta(minutes=0, hours=8)

        to_go = reference_time - working_time

        return to_go

    def _calculate_working_time(self):
        working_time = datetime.timedelta()

        if self._check_date_exist(self.working_time):
            for elements in self.working_time[self.now_date]:
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

        for date in self.overtimes.keys():
            if month in date:
                msg = "{}{}: {}\n".format(msg, date, self.overtimes[date])

        if msg:
            msg = "Overtimes in: '{}'\n\n{}".format(month, msg)
        else:
            msg = "No overtimes in current month."

        MessageBox.show(text=msg)

    def _edit_times(self, file_path):
        try:
            subprocess.run([TXT_EDITOR, file_path])
        except Exception as exc:
            MessageBox.show(
                text=str(exc),
                title="Error",
                icon=QMessageBox.Critical,
                detailed_text=str(type(exc))
            )

        self.working_time = JsonHelpers.read_file(file_path)
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

        self.activity = ActivityLogger()

        self.tray = self._prepare_tray_menu()
        self._update_tooltip_text()
        self.tray.show()

        self.overtime_timer = self._prepare_overtime_check_timer()
        self.overtime_timer.start()

        self.activity_timer = self._prepare_activity_logger_timer()
        self.activity_timer.start()

    def _prepare_tray_menu(self):
        tray = QSystemTrayIcon(QIcon("icon.png"), self.app)
        menu = QMenu()

        menu = self._set_tray_menu_item(menu, "Log break", self._log_time)
        menu = self._set_tray_menu_item(menu, "Working time", self._show_working_time)

        menu.addSeparator()

        menu = self._set_tray_menu_item(menu, "Show logs", self._get_today_log)
        menu = self._set_tray_menu_item(menu, "Show overtimes", self._show_overtimes)
        menu = self._set_tray_menu_item(menu, "Show activity", self._show_activity)

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

    def _prepare_activity_logger_timer(self):
        timer = QTimer()
        timer.setInterval(1 * 1000)
        timer.timeout.connect(self._check_activity)

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

    def _show_activity(self):
        self.activity.show_activity()

    def _edit_logs(self):
        self.time.edit_logs()
        self._update_tooltip_text()

    def _edit_overtimes(self):
        self.time.edit_overtimes()
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
        self.time.log_time(exit=True)

        sys.exit(status)

    def _check_overtime(self):
        global MSG_BOX_SHOWED
        working_time = self.time._calculate_working_time()

        if working_time > self.time.reference_time:
            if not MSG_BOX_SHOWED:
                msg = "It's time to end your work.\n\n{}".format(working_time)
                MessageBox.show(text=msg)
                MSG_BOX_SHOWED = True
            overtimes = working_time - self.time.reference_time

            self._save_overtimes(overtimes)
        self._update_tooltip_text()

    def _check_activity(self):
        self.activity.run()

    def _save_overtimes(self, overtimes):
        now = datetime.datetime.now()
        now_date = str(now.strftime("%Y/%m/%d"))

        self.time.overtimes[now_date] = str(overtimes)
        JsonHelpers.write_file(OVERTIMES_PATH, self.time.overtimes)

        self.time.working_time[now_date][-1]["END"] = str(datetime.datetime.now().strftime("%H:%M:%S"))
        JsonHelpers.write_file(FILE_PATH, self.time.working_time)


if __name__ == '__main__':
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = App()
    app.run()
