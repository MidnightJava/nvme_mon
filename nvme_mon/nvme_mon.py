import re
from collections import namedtuple
from datetime import datetime
from operator import attrgetter
from statistics import mean, median
from collections import defaultdict

LOG_FILE = "/var/log/SSD1_temp.log"
REC_PATTERN = r"(\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2})\s+Sensor (\d)\s(\d+)$"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

Record = namedtuple('LogRecord', ['datetime', 'temp'])

def histo_record():
    return {"count": 0, "last_date": datetime(1970, 1, 1)}

class NvmeInfo:

    def __init__(self):
        self._start_date = datetime.today()
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

    @property
    def start_date(self):
        return self._start_date
    
    @start_date.setter
    def start_date(self, start_date):
        self._start_date = datetime.strptime(start_date, DATE_FORMAT)
    @property
    def num_days(self):
        return (datetime.today() - self.start_date).days


class NvmeMon:

    def __init__(self, log_file):
        self.log_file = log_file
        self.s1_records = []
        self.s2_records = []

    def parse_log(self):
        with open(self.log_file) as f:
            for line in f.readlines():
                m = re.match(REC_PATTERN, line)
                if m:
                    _datetime = m.group(1)
                    _sensor = int(m.group(2))
                    _temp = int(m.group(3).strip())
                    if _sensor == 1:
                        self.s1_records.append(Record(_datetime, _temp))
                    elif _sensor == 2:
                        self.s2_records.append(Record(_datetime, _temp))

    def display_records(self):
        
        ### Start Date ###
        start_dates = []
        if len(self.s1_records):
            self.s1_records = sorted(self.s1_records, key=attrgetter('datetime'))
            start_dates.append(self.s1_records[0].datetime)
        if len(self.s2_records):
            self.s2_records = sorted(self.s2_records, key=attrgetter('datetime'))
            start_dates.append(self.s2_records[0].datetime)
        start_date = sorted(start_dates)[0]

        all_records = [*self.s1_records, *self.s2_records]

        ### Min Temp ###
        min_temp = min(map(lambda t: t.temp, all_records))

        ### Mean and Median Temps ###
        mean_temp = mean(map(lambda t: int(t.temp), all_records))
        median_temp = median(map(lambda t: int(t.temp), all_records))

        ### Max Temp ###
        max_temp = max(map(lambda t: t.temp, all_records))

        ### Last Date of Max Temp ###
        max_temp_dates = [datetime.strptime(t.datetime, DATE_FORMAT) for t in all_records if t.temp == max_temp]
        max_temp_date =  sorted(max_temp_dates)[-1]

        s1_histogram = defaultdict(histo_record)
        for record in self.s1_records:
            histo_entry = s1_histogram[record.temp]
            histo_entry["count"] += 1
            histo_entry["last_date"] = max(datetime.strptime(record.datetime, DATE_FORMAT), histo_entry["last_date"])

        s2_histogram = defaultdict(histo_record)
        for record in self.s2_records:
            histo_entry = s2_histogram[record.temp]
            histo_entry["count"] += 1
            histo_entry["last_date"] = max(datetime.strptime(record.datetime, DATE_FORMAT), histo_entry["last_date"])
        


        info = NvmeInfo()
        info.start_date = start_date
        info.min = min_temp
        info.max = max_temp
        info.max_temp_date = max_temp_date
        info.mean = int(mean_temp)
        info.median = median_temp
        info.histograms[1] = dict(sorted(s1_histogram.items(), reverse=True))
        info.histograms[2] = dict(sorted(s2_histogram.items(), reverse=True))

        print(f"Start Date: {info.start_date.date()}")
        print(f"Num Days: {info.num_days}")
        print(f"Min temp: {info.min}")
        print(f"Max temp: {info.max}")
        print(f"Max temp datetime: {info.max_temp_date}")
        print(f"Mean temp: {info.mean}")
        print(f"Median temp: {info.median}")
        print("S1 historgram")
        for k,v in info.histograms[1].items():
            print(f"{k}: {v["count"]}  {datetime.strftime(v["last_date"], DATE_FORMAT)}")
        print()
        print("S2 historgram")
        for k,v in info.histograms[2].items():
            print(f"{k}: {v["count"]}  {datetime.strftime(v["last_date"], DATE_FORMAT)}")
       

if __name__ == '__main__':
    mon = NvmeMon(LOG_FILE)
    mon.parse_log()
    mon.display_records()