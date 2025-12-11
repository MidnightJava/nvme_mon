#!/usr/bin/env python3
import os, sys, tty, termios
from collections import namedtuple, defaultdict
from datetime import datetime
from operator import attrgetter
from statistics import mean, median
import rich_ui
import json
from itertools import cycle
import time

LOG_FILE = "/var/log/nvme_health.json"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

Record = namedtuple('LogRecord', ['datetime', 'temp'])

def histo_record():
    return {"count": 0, "last_date": datetime(1970, 1, 1)}

def device_record():
    return {"histogram": defaultdict(histo_record), "temp_info": {}, "health_info": {}}

def clear_screen():
     print("\033[H\033[2J")

def getkey():
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    try:
        b = os.read(sys.stdin.fileno(), 3).decode()
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
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

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
        self.median_sample_interval = 0

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
        self.top_five=True

        self.parse_log_file()
        # start display (which also starts the listener)
        self.display_info()

    def parse_log_file(self):
        self.devices = defaultdict(device_record)
        temp_records = defaultdict(list)
        with open(self.log_file, 'r') as f:
            for line in f:
                record = json.loads(line)
                device = record["device"]
                histo_entry = self.devices[device]["histogram"][record["mean_temperature"]]
                histo_entry["count"] += 1
                histo_entry["last_date"] = max(datetime.strptime(record["timestamp"], DATE_FORMAT), histo_entry["last_date"])
                temp_records[device].append(Record(record["timestamp"], record["mean_temperature"]))
                if self.last_sample_time[device] is not None:
                    delta = (datetime.strptime(record["timestamp"], DATE_FORMAT) - self.last_sample_time[device]).seconds
                    self.sample_intervals[device].append(delta)
                self.last_sample_time[device] = datetime.strptime(record["timestamp"], DATE_FORMAT)
                self.devices[device]["health_info"] = self.get_health_info(record)
            for device in self.devices.keys():
                self.devices[device]["temp_info"] = self.get_temp_info(device, temp_records[device])

    def get_temp_info(self, device, temp_records):
        start_date = sorted(temp_records, key=attrgetter('datetime'))[0]
        min_temp = min(map(lambda t: int(t.temp), temp_records))
        mean_temp = mean(map(lambda t: int(t.temp), temp_records))
        median_temp = median(map(lambda t: int(t.temp), temp_records))
        max_temp = max(map(lambda t: int(t.temp), temp_records))
        max_temp_dates = [datetime.strptime(t.datetime, DATE_FORMAT) for t in temp_records if int(t.temp) == max_temp]
        max_temp_date = sorted(max_temp_dates)[-1]
        median_sample_delta = median(self.sample_intervals[device]) if self.sample_intervals[device] else 0

        info = NvmeInfo()
        info.device_name = device
        info.start_date = start_date.datetime
        info.min = min_temp
        info.max = max_temp
        info.max_temp_date = max_temp_date
        info.mean = int(mean_temp)
        info.median = int(median_temp)
        info.median_sample_interval = int(median_sample_delta)

        return info

    def get_health_info(self, record):
        return {
            "power_on_hours": record.get("power_on_hours"),
            "unsafe_shutdowns": record.get("unsafe_shutdowns"),
            "media_errors": record.get("media_errors"),
            "num_err_log_entries": record.get("num_err_log_entries"),
            "percentage_used": record.get("percent_used"),
            "health_score": record.get("health_score")
        }

    def get_devices(self):
        for _, device in cycle(self.devices.items()):
            yield device

    def display_info(self):

        current_device = None
        for device in self.get_devices():
            clear_screen()
            if current_device is not None and device != current_device:
                continue
            current_device = None
            temp_info = device["temp_info"]
            health_info = device["health_info"]
            health_info["Device"] = os.path.basename(temp_info.device_name)
            health_info["Log Data"] = f"{temp_info.num_days} day{'' if temp_info.num_days == 1 else 's'}, beginning {temp_info.start_date.date()}"
            data = health_info
            rich_ui.print_health_info(data, box=True, title="Disk Health Info")

            data = {
                "Min temp": temp_info.min,
                "Max temp": temp_info.max,
                "Max temp datetime": temp_info.max_temp_date,
                "Mean temp": temp_info.mean,
                "Median temp": temp_info.median,
                "Median sample interval": f"{temp_info.median_sample_interval} sec"
            }
            rich_ui.print_temp_info(data, box=True, title="Summary Temperature Info (Based on average of all sensor readings)")

            histo = device["histogram"]
            histo = dict(sorted(histo.items(), key=self.SORT_KEYS[self.CURRENT_SORT_KEY_IDX]["value"], reverse=True))
            if self.top_five:
                histo = dict(list(histo.items())[:5])
            rich_ui.print_histogram(
                histo,
                dt_display=self.dt_display,
                max_width=60,
                sort_key=self.SORT_KEYS[self.CURRENT_SORT_KEY_IDX]["name"],
                box=True,
                spacing=1, title=f"Temperature Histogram")

            # Wait until Tab is pressed. Blocks here (no busy-wait).
            print("Press Tab to cycle through the devices, s to rotate histogram sort key, t to toggle between date and date-time, r to toggle top or all results, q to quit, ")
            
            key = getkey()
            if key == 'q':
                sys.exit(0)
            elif key == 's':
                self.CURRENT_SORT_KEY_IDX = (self.CURRENT_SORT_KEY_IDX + 1) % len(self.SORT_KEYS)
                current_device = device
                continue
            elif key == 'r':
                self.top_five = False if self.top_five else True
                current_device = device
                continue
            elif key == 't':
                self.dt_display = 'datetime' if self.dt_display == 'date' else 'date'
                current_device = device
                continue
            while key != 'tab':
                key = getkey()
                time.sleep(0.5)

if __name__ == '__main__':
    mon = NvmeMon(LOG_FILE)
