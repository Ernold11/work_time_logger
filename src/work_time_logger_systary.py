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
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "log.txt")
OVERTIMES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "overtimes.txt")


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
                    print(working_time)
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
        lines = list()
        msg = "{}: {}\n".format(now_date, overtimes)

        try:
            with open(OVERTIMES_PATH, "r") as f:
                lines = f.readlines()
                if now_date in lines[-1]:
                    lines[-1] = msg
                else:
                    lines.append(msg)
        except:
            lines.append(msg)

        with open(OVERTIMES_PATH, "w") as f:
            for line in lines:
                f.write("{}".format(line))
                print(line)

        print("SAVED_OVERTIMES: '{}'".format(msg))


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
        date_exists = False
        msg = ""

        with open(FILE_PATH, "r") as f:
            for line in f.readlines():
                if self.now_date in line:
                    date_exists = True
                if date_exists:
                    msg = "{}{}".format(msg, line)

        if date_exists:
            wx.MessageBox("Today logged times:\n\n{}".format(msg), 'Info', wx.OK | wx.ICON_INFORMATION)
        else:
            wx.MessageBox("Not logged any time!", 'Info', wx.OK | wx.ICON_INFORMATION)

    def log_work(self, msgBox=True, first_run=False):
        now = datetime.datetime.now()
        self.now_date = str(now.strftime("%Y/%m/%d"))
        now_time = str(now.strftime("%H:%M:%S"))

        date_exists, last_time = self._get_last_time_if_exist()
        self._write_time_to_file(date_exists, now_time, last_time, first_run)

        with open(FILE_PATH) as f:
            for line in f.readlines():
                print("{}\n".format(line))

        if msgBox:
            wx.MessageBox("Logged time:\n\n{} {}".format(self.now_date, now_time), 'Info', wx.OK | wx.ICON_INFORMATION)

    def _get_last_time_if_exist(self):
        date_exists = False
        last_time = None

        try:
            with open(FILE_PATH, "r") as f:
                for line in f.readlines():
                    line = line.replace("\t", "")

                    if self.now_date in line:
                        date_exists = True
                    if line and line.strip() and date_exists:
                        last_time = line.split(' ')[0].strip()
            print("LAST TIME: '{}'".format(last_time))
        except:
            pass

        return date_exists, last_time

    def _write_time_to_file(self, date_exists, now_time, last_time, first_run):
        arrow = "-->"
        skip = False

        with open(FILE_PATH, "a") as f:
            if not date_exists:
                f.write("{}\n".format(self.now_date))

            if last_time == "-->" and not first_run:
                arrow = "<--"
            elif last_time == "-->" and first_run:
                skip = True

            if arrow == "-->":
                self.log_label = "Log break"
            else:
                self.log_label = "Log work"

            if not skip:
                f.write("\t{} {}\n".format(arrow, now_time))

    def show_working_time(self, event, silent_mode=False):
        working_time = self._calculate_working_time()
        overtime = False

        delta = self._calculate_time_left(working_time, self.reference_time)
        self.set_icon()
        end_time = now = datetime.datetime.now() + delta

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
        start, end, working_time = self._get_working_time_details()

        if start and not end:
            now = datetime.datetime.now()
            end = str(now.strftime("%H:%M:%S"))
            end = datetime.datetime.strptime(end, '%H:%M:%S')

            curr_delta = end - start
            working_time += curr_delta
        elif not start:
            msg = "Not found start time in current day."
            wx.MessageBox(msg, 'Info', wx.OK | wx.ICON_INFORMATION)
            global MSG_BOX_SHOWED
            MSG_BOX_SHOWED = False
            self.log_work(msgBox=False)

        print("FINAL DELTA: '{}'\n".format(working_time))

        return working_time

    def _get_working_time_details(self):
        now = datetime.datetime.now()
        now_date = str(now.strftime("%Y/%m/%d"))
        working_time = datetime.timedelta()
        date_exists = False
        start = None
        end = None

        with open(FILE_PATH, "r") as f:
            for line in f.readlines():
                if now_date in line:
                    date_exists = True
                    continue
                if date_exists:
                    start, end, working_time = self._calculate_working_time_details(start, end, working_time, line)

        return start, end, working_time

    def _calculate_working_time_details(self, start, end, working_time, line):
        if "-->" in line:
            start = line.replace("-->", "").strip()
            print("START_TIME: '{}'".format(start))
            start = datetime.datetime.strptime(start, '%H:%M:%S')
        elif "<--" in line:
            end = line.replace("<--", "").strip()
            print("END_TIME: '{}'".format(end))
            end = datetime.datetime.strptime(end, '%H:%M:%S')

        if start and end:
            curr_delta = end - start
            start = None
            end = None

            print("DELTA: '{}'".format(str(curr_delta)))
            working_time += curr_delta

        return start, end, working_time

    def show_overtimes(self, event):
        now = datetime.datetime.now()
        month = str(now.strftime("%Y/%m"))
        lines = list()
        msg = ""

        try:
            with open(OVERTIMES_PATH, "r") as f:
                for line in f.readlines():
                    if month in line:
                        msg = "{}{}".format(msg, line)
        except:
            pass

        if msg:
            msg = "Overtimes in: '{}'\n\n{}".format(month, msg)
        else:
            msg = "No overtimes in current month."

        wx.MessageBox(msg, 'Info', wx.OK | wx.ICON_INFORMATION)

    def _edit_times(self, file_path):
        try:
            subprocess.run([TXT_EDITOR, file_path])
        except Exception as exc:
            print("Caught exception: '{}'".format(exc))

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
        frame = wx.Frame(None)
        self.SetTopWindow(frame)
        self.task_bar_icon = TaskBarIcon(frame, STOP_MODE)
        return True

    def InitLocale(self):
        self.ResetLocale()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Log work time")

    parser.add_argument('--stop', required=False, action='store_true', help="Use when stop application.",
                        default=False)

    args = parser.parse_args()

    STOP_MODE = args.stop

    app = App(False)
    app.MainLoop()
