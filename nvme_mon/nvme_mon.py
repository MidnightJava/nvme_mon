#!/usr/bin/env python3
import re
from collections import namedtuple, defaultdict
from datetime import datetime
from operator import attrgetter
from statistics import mean, median
import histogram
import json
import time
import threading
from pynput.keyboard import Key, Listener

LOG_FILE = "/var/log/nvme_health.json"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

Record = namedtuple('LogRecord', ['datetime', 'temp'])

def histo_record():
    return {"count": 0, "last_date": datetime(1970, 1, 1)}

def device_record():
    return {"histogram": defaultdict(histo_record), "temp_info": {}, "health_info": {}}

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
    def __init__(self, log_file):
        # set up attributes early
        self.log_file = log_file
        self.tab_event = threading.Event()      # use Event instead of boolean
        self.infos = []
        self.last_sample_time = defaultdict(lambda: None)
        self.sample_intervals = defaultdict(list)

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
        for _, device in self.devices.items():
            yield device

    # callback from pynput
    def on_press(self, key):
        print(f"on_press callback: {key!r}")
        print("Raw key event:", repr(key), type(key))

        # Case 1: tab reported as Key.tab
        if key == Key.tab:
            self.tab_event.set()
            return

        # Case 2: tab reported as a char ('\t')
        try:
            if hasattr(key, 'char') and key.char == '\t':
                self.tab_event.set()
                return
        except:
            pass


    def display_info(self):
        # start listener thread BEFORE we enter device-processing loop
        listener = Listener(on_press=self.on_press)
        listener.start()
        print("\033[H\033[2J")

        try:
            for device in self.get_devices():
                temp_info = device["temp_info"]
                health_info = device["health_info"]
                health_info["Device"] = temp_info.device_name
                health_info["Log Data"] = f"{temp_info.num_days} day{'' if temp_info.num_days == 1 else 's'}, beginning {temp_info.start_date.date()}"
                data = health_info
                histogram.print_health_info(data, box=True, title="Disk Health Info")

                data = {
                    "Min temp": temp_info.min,
                    "Max temp": temp_info.max,
                    "Max temp datetime": temp_info.max_temp_date,
                    "Mean temp": temp_info.mean,
                    "Median temp": temp_info.median,
                    "Median sample interval": f"{temp_info.median_sample_interval} sec"
                }
                histogram.print_temp_info(data, box=True, title="Current Temperature Info (Based on average of all sensor readings)")

                histo = device["histogram"]
                histo = dict(sorted(histo.items(), key=None, reverse=True))
                histogram.print_histogram(histo, max_width=60, box=True, spacing=1, title=f"Temperature Histogram")

                # Wait until Tab is pressed. Blocks here (no busy-wait).
                print("Press TAB to continue to the next device...")
                self.tab_event.wait()        # blocks until .set() called in callback
                print("Continuing after TAB")
                # reset for next device
                self.tab_event.clear()

        finally:
            # ensure we stop the listener when done (or on exception)
            listener.stop()


if __name__ == '__main__':
    import os
    print("Running as UID:", os.getuid())

    mon = NvmeMon(LOG_FILE)
