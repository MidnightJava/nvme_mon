import re
from collections import namedtuple
from datetime import datetime
from operator import attrgetter
from statistics import mean, median
from collections import defaultdict
import histogram
import json
import math

LOG_FILE = "/var/log/nvme_health.json"
REC_PATTERN = r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+Sensor (\d)\s(\d+)$"
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
        self.histograms = {
            1: [],
            2: []
        }
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
        self.log_file = log_file
        self.infos = []
        self.last_sample_time = defaultdict(lambda: None)
        self.sample_intervals = defaultdict(list)
        self.parse_log_file()
        self.display_info()
        

    def parse_log_file(self):
        self.devices = defaultdict(device_record)
        temp_records = defaultdict(list)
        with open(self.log_file, 'r') as f:
            for line in f.readlines():
                record = json.loads(line)
                device = record["device"]
                histo_entry = self.devices[device]["histogram"][record["mean_temperature"]]
                histo_entry["count"] += 1
                histo_entry["last_date"] = max(datetime.strptime(record["timestamp"], DATE_FORMAT), histo_entry["last_date"])
                temp_records[device].append(Record(record["timestamp"], record["mean_temperature"]))
                if self.last_sample_time[device] is not None:
                     self.sample_intervals[device].append(
                        (datetime.strptime(record["timestamp"], DATE_FORMAT) - self.last_sample_time[device]).seconds)
                self.last_sample_time[device] = datetime.strptime(record["timestamp"], DATE_FORMAT)
                self.devices[device]["health_info"] = self.get_health_info(record)
            for device in self.devices.keys():
                self.devices[device]["temp_info"] = self.get_temp_info(device, temp_records[device])

    def get_temp_info(self, device, temp_records):
        start_date = sorted(temp_records, key=attrgetter('datetime'))[0]
        min_temp = min(map(lambda t: t.temp, temp_records))

        ### Mean and Median Temps ###
        mean_temp = mean(map(lambda t: int(t.temp), temp_records))
        median_temp = median(map(lambda t: int(t.temp), temp_records))

        ### Max Temp ###
        max_temp = max(map(lambda t: t.temp, temp_records))

        ### Last Date of Max Temp ###
        max_temp_dates = [datetime.strptime(t.datetime, DATE_FORMAT) for t in temp_records if t.temp == max_temp]
        max_temp_date =  sorted(max_temp_dates)[-1]

        # Collection Period
        median_sample_delta = median(self.sample_intervals[device])

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
        return {"power_on_hours": record.get("power_on_hours"),
        "unsafe_shutdowns": record.get("unsafe_shutdowns"),
        "media_errors": record.get("media_errors"),
        "num_err_log_entries": record.get("num_err_log_entries"),
        "percentage_used": record.get("percent_used"),
        "health_score": record.get("health_score")
        }

    def display_info(self):
        print("\033[H\033[2J")
        for _, device in self.devices.items():
            temp_info = device["temp_info"]
            health_info = device["health_info"]
            histo = device["histogram"]
            print(f"Device: {temp_info.device_name}")
            print(f"Log Data: {temp_info.num_days} day{'' if temp_info.num_days == 1 else 's'}, beginning {temp_info.start_date.date()}")
            print("Disk Health Info")
            for k,v in health_info.items():
                print(f"{k}: {v}")
            print("Current Temperature Info (Based on average of all sensor readings)")
            print(f"Min temp: {temp_info.min}")
            print(f"Max temp: {temp_info.max}")
            print(f"Max temp datetime: {temp_info.max_temp_date}")
            print(f"Mean temp: {temp_info.mean}")
            print(f"Median temp: {temp_info.median}")
            print(f"Median sample interval: {temp_info.median_sample_interval} sec")
            device_name = device["temp_info"].device_name
            histogram.print_histogram(histo, max_width=60, box=True, spacing=1, title=f"Temperature Histogram")

if __name__ == '__main__':
    mon = NvmeMon(LOG_FILE)