import datetime
import wx.adv
import wx
import os
import sys
import threading
import time
import json
import argparse
import subprocess

TXT_EDITOR = "notepad.exe"
TRAY_TOOLTIP = 'Work time logger\n{}'
FINISH_WORK = threading.Event()
STOP_MODE = False
MSG_BOX_SHOWED = False
TRAY_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icon.png')
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.json")
OVERTIMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overtimes.json")


class JsonHelpers:
    @staticmethod
    def read_file(file_path):
        """
        Read content from specific json file.
        :param json_path: path to json file.
        :return: loaded json content.
        """
        try:
            with open(file_path, 'r') as fp:
                return json.load(fp)
        except Exception as exc:
            wx.MessageBox(str(exc), "Error", wx.OK | wx.ICON_ERROR)
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
            wx.MessageBox(str(exc), "Error", wx.OK | wx.ICON_ERROR)


class MyThread(threading.Thread):
    def __init__(self, calculate_working_time, reference_time, show_working_time, set_icon):
        threading.Thread.__init__(self)
        self.calculate_working_time = calculate_working_time
        self.reference_time = reference_time
        self.show_working_time = show_working_time
        self.set_icon = set_icon

    def run(self):
        overtimes = datetime.timedelta()
        finished = False
        global MSG_BOX_SHOWED

        while not finished:
            working_time = self.calculate_working_time()

            if working_time > self.reference_time:
                if not MSG_BOX_SHOWED:
                    wx.MessageBox("It's time to end your work.\n\n{}".format(working_time), 'Info',
                                  wx.OK | wx.ICON_INFORMATION)
                    MSG_BOX_SHOWED = True
                overtimes = working_time - self.reference_time

                self.save_overtimes(overtimes)
            self.show_working_time(event=None, silent_mode=True)
            self.set_icon()
            finished = FINISH_WORK.wait(timeout=60)

    def save_overtimes(self, overtimes):
        now = datetime.datetime.now()
        now_date = str(now.strftime("%Y/%m/%d"))

        data = JsonHelpers.read_file(OVERTIMES_PATH)
        data[now_date] = overtimes
        JsonHelpers.write_file(data)

        data = JsonHelpers.read_file(FILE_PATH)
        data[now_date][-1]["END"] = str(datetime.datetime.now().strftime("%H:%M:%S"))
        JsonHelpers.write_file(data)


class TaskBarIcon(wx.adv.TaskBarIcon):
    def __init__(self, frame, stop_mode):
        super(TaskBarIcon, self).__init__()
        self.frame = frame
        if stop_mode:
            self.on_exit(event=None, msgBox=False)
            sys.exit()
        self.log_work(msgBox=False, first_run=True)
        self.reference_time = datetime.timedelta(minutes=0, hours=8)
        self.time_left = ""
        self.show_working_time(event=None, silent_mode=True)
        self.set_icon()
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
        self.worker = MyThread(self._calculate_working_time, self.reference_time, self.show_working_time, self.set_icon)
        self.worker.start()
        self.log_label = "Log break"
        self.now_date = str(datetime.datetime.now().strftime("%Y/%m/%d"))

    def create_menu_item(self, menu, label, func):
        item = wx.MenuItem(menu, -1, label)
        menu.Bind(wx.EVT_MENU, func, id=item.GetId())
        menu.Append(item)

    def CreatePopupMenu(self):
        menu = wx.Menu()
        self.create_menu_item(menu, self.log_label, self.log_work)
        self.create_menu_item(menu, 'Working time', self.show_working_time)
        menu.AppendSeparator()
        self.create_menu_item(menu, 'Show logs', self.load_today_logs)
        self.create_menu_item(menu, 'Show overtimes', self.show_overtimes)
        menu.AppendSeparator()
        self.create_menu_item(menu, 'Edit logs', self.edit_logs)
        self.create_menu_item(menu, 'Edit overtimes', self.edit_overtimes)
        menu.AppendSeparator()
        self.create_menu_item(menu, 'Exit', self.on_exit)

        return menu

    def set_icon(self):
        icon = wx.Icon(TRAY_ICON)
        self.SetIcon(icon, TRAY_TOOLTIP.format(self.time_left))

    def on_left_down(self, event):
        # self.log_work()
        pass

    def load_today_logs(self, event):
        msg = ""

        data = JsonHelpers.read_file(FILE_PATH)
        date_exists = self._check_date_exist(data)

        if date_exists:
            for elements in data[self.now_date]:
                for element_name, element_value in elements.items():
                    msg = "{}{}:{}\n".format(msg, element_name, element_value)

        if date_exists:
            wx.MessageBox("Today logged times:\n\n{}".format(msg), 'Info', wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("Not logged any time!", 'Info', wx.OK | wx.ICON_INFORMATION)

    def log_work(self, msgBox=True, first_run=False):
        now = datetime.datetime.now()
        self.now_date = str(now.strftime("%Y/%m/%d"))
        now_time = str(now.strftime("%H:%M:%S"))

        self._write_time_to_file(now_time, first_run)

        if msgBox:
            wx.MessageBox("Logged time:\n\n{} {}".format(self.now_date, now_time), 'Info', wx.OK | wx.ICON_INFORMATION)

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

    def show_working_time(self, event, silent_mode=False):
        working_time = self._calculate_working_time()
        overtime = False

        delta = self._calculate_time_left(working_time, self.reference_time)
        self.set_icon()
        end_time = datetime.datetime.now() + delta

        end_time = end_time.strftime("%H:%M:%S")

        if working_time > self.reference_time:
            delta = working_time - self.reference_time
            overtime = True

        if working_time:
            msg = "Summary working time:\n\nWorking time: {}\n".format(working_time)
            if not overtime:
                msg = "{}Time left: {}\nEstimated end work: {}\n".format(msg, delta, end_time)
                self.time_left = "Time left: {}".format(delta)
            elif overtime:
                msg = "{}Overtimes: {}".format(msg, delta)
                self.time_left = "Overtimes: {}".format(delta)
        if not silent_mode:
            wx.MessageBox(msg, 'Info', wx.OK | wx.ICON_INFORMATION)

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
            wx.MessageBox(msg, 'Info', wx.OK | wx.ICON_INFORMATION)
            global MSG_BOX_SHOWED
            MSG_BOX_SHOWED = False
            self.log_work(msgBox=False)

        return working_time

    def show_overtimes(self, event):
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

        wx.MessageBox(msg, 'Info', wx.OK | wx.ICON_INFORMATION)

    def _edit_times(self, file_path):
        try:
            subprocess.run([TXT_EDITOR, file_path])
        except Exception as exc:
            wx.MessageBox(str(exc), "Error", wx.OK | wx.ICON_ERROR)

        self.show_working_time(event=None, silent_mode=True)

    def edit_logs(self, event):
        self._edit_times(FILE_PATH)

    def edit_overtimes(self, event):
        self._edit_times(OVERTIMES_PATH)

    def on_exit(self, event, msgBox=True):
        FINISH_WORK.set()
        self.log_work(msgBox=msgBox)
        wx.CallAfter(self.Destroy)
        self.frame.Close()


class App(wx.App):
    def OnInit(self):
        # locale = wx.Locale("en-US")
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        self.task_bar_icon = TaskBarIcon(frame, STOP_MODE)
        return True

    # def InitLocale(self):
    #     self.ResetLocale()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Log work time")

    parser.add_argument('--stop', required=False, action='store_true', help="Use when stop application.",
                        default=False)

    args = parser.parse_args()

    STOP_MODE = args.stop

    app = App(False)
    app.MainLoop()
