import re
from collections import namedtuple
from datetime import datetime
from operator import attrgetter

LOG_FILE = "/var/log/SSD1_temp.log"
REC_PATTERN = r"(.*)\s(.*)\sSensor (\d)\s(.*)"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

Record = namedtuple('LogRecord', ['date', 'time', 'temp'])

class NvmeInfo:

    def __init__(self):
        self._start_date = datetime.today()
        self.ave = 0
        self.mean = 0
        self.hisograms = {
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
                    _date = m.group(1)
                    _time = m.group(2)
                    _sensor = int(m.group(3))
                    _temp = m.group(4)
                    if _sensor == 1:
                        self.s1_records.append(Record(_date, _time, _temp))
                    elif _sensor == 2:
                        self.s2_records.append(Record(_date, _time, _temp))

    def display_records(self):
        # print("Sensor 1 records")
        # for record in self.s1_records:
        #     print(record.date, record.time, record.temp)
        # print("Sensor 2 records")
        # for record in self.s2_records:
        #     print(record.date, record.time, record.temp)
        
        start_dates = []
        if len(self.s1_records):
            self.s1_records = sorted(self.s1_records, key=attrgetter('date'))
            start_dates.append(self.s1_records[0].date)
        if len(self.s2_records):
            self.s2_records = sorted(self.s2_records, key=attrgetter('date'))
            start_dates.append(self.s2_records[0].date)

        start_date = sorted(start_dates)[0]

        info = NvmeInfo()
        info.start_date = start_date

        print(f"Start Date: {info.start_date}")
        print(f"Num Days: {info.num_days}")



if __name__ == '__main__':
    mon = NvmeMon(LOG_FILE)
    mon.parse_log()
    mon.display_records()