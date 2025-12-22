#!/usr/bin/env python3
import os, sys, tty, termios, select
from os import path
from pathlib import Path
from collections import namedtuple, defaultdict
from datetime import datetime
from operator import attrgetter
from statistics import mean, median
import rich_ui
import json
from itertools import cycle
import time
import fcntl

from alert_manager import AlertManager

from rich_ui import YELLOW_THRESHOLD, RED_THRESHOLD

LOG_FILE = "/var/log/nvme_health.json"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

REFRESH_INTERVAL_SEC = 60

Record = namedtuple('LogRecord', ['datetime', 'temp'])

def histo_record():
    return {"count": 0, "last_date": datetime(1970, 1, 1)}

def device_record():
    return {"histogram": defaultdict(histo_record), "temp_info": {}, "health_info": {}}

def clear_screen():
     print("\033[H\033[2J")

def getkey(timeout=5):
    fd = sys.stdin.fileno()

    old_term = termios.tcgetattr(fd)
    old_flags = fcntl.fcntl(fd, fcntl.F_GETFL)

    tty.setcbreak(fd)
    fcntl.fcntl(fd, fcntl.F_SETFL, old_flags | os.O_NONBLOCK)

    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            # print(time.monotonic(), deadline)
            try:
                b = os.read(fd, 3)
                if b:
                    b = b.decode(errors="ignore")
                    if len(b) == 3:
                        k = ord(b[2])
                    else:
                        k = ord(b)

                    key_mapping = {
                        127: 'backspace',
                        10: 'return',
                        32: 'space',
                        9: 'tab',
                        27: 'esc',
                        65: 'up',
                        66: 'down',
                        67: 'right',
                        68: 'left'
                    }

                    return key_mapping.get(k, chr(k))
            except BlockingIOError as e:
                pass

            time.sleep(0.01)  # avoid busy spin
        return None  # timeout

    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_term)
        fcntl.fcntl(fd, fcntl.F_SETFL, old_flags)


class NvmeInfo:
    def __init__(self):
        self._start_date = datetime.today()
        self.device_name = ""
        self.ave = 0
        self.min = 0
        self.max = 0
        self.max_temp_date = ""
        self.mean = 0
        self.median = 0
        self.histograms = {1: [], 2: []}
        self.median_sample_interval = None
        self.current_sample_interval = None

    @property
    def start_date(self):
        return self._start_date

    @start_date.setter
    def start_date(self, start_date):
        self._start_date = datetime.strptime(start_date, DATE_FORMAT)

    @property
    def num_days(self):
        return (datetime.today() - self.start_date).days + 1


class NvmeMon:
    global CURRENT_SORT_KEY_IDX
    global SORT_KEYS
    def __init__(self, log_file):
        # set up attributes early
        self.log_file = log_file
        self.infos = []
        self.last_sample_time = defaultdict(lambda: None)
        self.sample_intervals = defaultdict(list)
        self.SORT_KEYS = [
            {"name": "Temperature", "value" :None}, #sort by temp
            {"name": "Last Occurrence", "value": lambda x: x[1]['last_date']}, #sort by last high temp date
            {"name": "Count", "value": lambda x: x[1]['count']} #sort by count
        ]
        self.dt_display = 'date'
        self.CURRENT_SORT_KEY_IDX = 0
        self.results_scope = [
            "top_5",
            "all",
            "yellow",
            "red",
        ]
        self.results_scope_idx = 0
        self.alert_manager = AlertManager()

        self.parse_log_file()
        # start display (which also starts the listener)
        self.display_info()

    def parse_log_file(self):
        self.devices = defaultdict(device_record)
        self.temp_records = defaultdict(list)
        with open(self.log_file, 'r') as f:
            for line in f:
                record = json.loads(line)
                device = record["device"]
                histo_entry = self.devices[device]["histogram"][record["mean_temperature"]]
                histo_entry["count"] += 1
                histo_entry["last_date"] = max(datetime.strptime(record["timestamp"], DATE_FORMAT), histo_entry["last_date"])
                self.temp_records[device].append(Record(record["timestamp"], record["mean_temperature"]))
                if self.last_sample_time[device] is not None:
                    delta = (datetime.strptime(record["timestamp"], DATE_FORMAT) - self.last_sample_time[device]).seconds
                    self.sample_intervals[device].append(delta)
                self.last_sample_time[device] = datetime.strptime(record["timestamp"], DATE_FORMAT)
                self.devices[device]["health_info"] = self.get_health_info(record)
            for device in self.devices.keys():
                self.devices[device]["temp_info"] = self.get_temp_info(device, self.temp_records[device])

    def get_temp_info(self, device, temp_records):
        start_date = sorted(temp_records, key=attrgetter('datetime'))[0]
        min_temp = min(map(lambda t: int(t.temp), temp_records))
        mean_temp = mean(map(lambda t: int(t.temp), temp_records))
        median_temp = median(map(lambda t: int(t.temp), temp_records))
        max_temp = max(map(lambda t: int(t.temp), temp_records))
        max_temp_dates = [datetime.strptime(t.datetime, DATE_FORMAT) for t in temp_records if int(t.temp) == max_temp]
        max_temp_date = sorted(max_temp_dates)[-1]
        median_sample_delta = median(self.sample_intervals[device]) if self.sample_intervals[device] else 0
        current_sample_delta = median(self.sample_intervals[device][-2:]) if self.sample_intervals[device] else 0

        info = NvmeInfo()
        info.device_name = device
        info.start_date = start_date.datetime
        info.min = min_temp
        info.max = max_temp
        info.max_temp_date = max_temp_date
        info.mean = int(mean_temp)
        info.median = int(median_temp)
        info.median_sample_interval = int(median_sample_delta)
        info.current_sample_interval = int(current_sample_delta)

        return info

    def get_health_info(self, record):
        return {
            "power_on_hours": record.get("power_on_hours"),
            "unsafe_shutdowns": record.get("unsafe_shutdowns"),
            "media_errors": record.get("media_errors"),
            "num_err_log_entries": record.get("num_err_log_entries"),
            "percentage_used": record.get("percentage_used"),
            "health_score": record.get("health_score"),
            "mean_temperature": record.get("mean_temperature")
        }
    
    def get_config(self):
        thresholds = {}
        config_file = path.join(Path(__file__).parent.resolve(), 'config')
        with open(config_file, 'r') as f:
            settings = {}
            parse_config = False
            parse_settings = False
            for line in f.readlines():
                if 'Alert Thresholds' in line:
                    parse_config = True
                elif 'Alert Settings' in line:
                    parse_settings = True
                    parse_config = False
                elif parse_config:
                    idx = line.find('#')
                    if idx > 0:
                        line = line[:idx]
                    if line.strip():
                        item = line.split(':')
                        thresholds[item[0].strip()] = int(item[1].strip())
                elif parse_settings:
                    idx = line.find('#')
                    if idx > 0:
                        line = line[:idx]
                    if line.strip():
                        item = line.split(':')
                        settings[item[0].strip()] = item[1].strip()
        return thresholds, settings
    
    # def get_current_temp(self, device):
    #     temps = dict(sorted(self.temp_records[device].items(), key= lambda x: x[1]['datetime'], reverse=True))
    #     return temps[0]['temp'] if temps else None
    
    def get_devices(self):
        for _, device in cycle(self.devices.items()):
            yield device

    def check_alerts(self, device):
        thresholds, settings = self.get_config()
        self.alert_manager.set_config(thresholds, settings)
        health_info = device["health_info"]
        self.alert_manager.send_alert(os.path.basename(device['temp_info'].device_name), health_info)

    def display_info(self):
        current_device = None
        for device in self.get_devices():
            clear_screen()
            if current_device is not None and device != current_device:
                continue
            current_device = None

            temp_info = device["temp_info"]

            data = {
                "Device": os.path.basename(temp_info.device_name),
                "Log Data":  f"{temp_info.num_days} day{'' if temp_info.num_days == 1 else 's'}, beginning {temp_info.start_date.date()}"
            }
            rich_ui.print_general_info(data)

            health_info = device["health_info"]
            data = health_info
            rich_ui.print_disk_info(data, box=True, title="Disk Health Info")

            data = {
                "Min temp": temp_info.min,
                "Max temp": temp_info.max,
                "Max temp datetime": temp_info.max_temp_date,
                "Mean temp": temp_info.mean,
                "Median temp": temp_info.median,
                "Sample interval (current/median)": f"{temp_info.current_sample_interval}/{temp_info.median_sample_interval} sec"
            }
            rich_ui.print_disk_info(data, box=True, title="Summary Temperature Info (Based on average of all sensor readings)")

            histo = device["histogram"]
            histo = dict(sorted(histo.items(), key=self.SORT_KEYS[self.CURRENT_SORT_KEY_IDX]["value"], reverse=True))
            if self.results_scope[self.results_scope_idx] == "top_5":
                histo = dict(list(histo.items())[:5])
            elif self.results_scope[self.results_scope_idx] == "yellow":
                histo = {k: v for k, v in histo.items() if k >= YELLOW_THRESHOLD}
            elif self.results_scope[self.results_scope_idx] == "red":
                histo = {k: v for k, v in histo.items() if k >= RED_THRESHOLD}
            rich_ui.print_histogram(
                histo,
                dt_display=self.dt_display,
                max_width=120,
                sort_key=self.SORT_KEYS[self.CURRENT_SORT_KEY_IDX]["name"],
                results_scope=self.results_scope[self.results_scope_idx],
                box=True,
                spacing=1, title=f"Temperature Histogram")

            rich_ui.render_prompt_text("Control keys: tab: next device, s: histogram sort, r: histogram results, t: date-time format, q: quit")
            
            key = getkey(REFRESH_INTERVAL_SEC)
            if key is None:
                for _device in self.devices.values():
                    self.check_alerts(_device)
                current_device = device
                continue
            if key == 'q':
                sys.exit(0)
            elif key == 's':
                self.CURRENT_SORT_KEY_IDX = (self.CURRENT_SORT_KEY_IDX + 1) % len(self.SORT_KEYS)
                current_device = device
                continue
            elif key == 'r':
                self.results_scope_idx = (self.results_scope_idx + 1) % len(self.results_scope)
                current_device = device
                continue
            elif key == 't':
                self.dt_display = 'datetime' if self.dt_display == 'date' else 'date'
                current_device = device
                continue
            elif key == 'tab':
                continue
            elif key == 'q':
                sys.exit(0)
            else:
                current_device = device

if __name__ == '__main__':
    mon = NvmeMon(LOG_FILE)
