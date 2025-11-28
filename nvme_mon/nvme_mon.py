import re
from collections import namedtuple

LOG_FILE = "/var/log/SSD1_temp.log"
REC_PATTERN = r"(.*)\s(.*)\sSensor \d\s(.*)"
Record = namedtuple('LogRecord', ['date', 'time', 'temp'])

class NvmeMon:

    def __init__(self, log_file):
        self.log_file = log_file
        self.records = []

    def parse_log(self):
        with open(self.log_file) as f:
            for line in f.readlines():
                m = re.match(REC_PATTERN, line)
                if m:
                    _date = m.group(1)
                    _time = m.group(2)
                    _temp = m.group(3)
                    self.records.append(Record(_date, _time, _temp))

    def display_records(self):
        for record in self.records:
            print(record.date, record.time, record.temp)



if __name__ == '__main__':
    mon = NvmeMon(LOG_FILE)
    mon.parse_log()
    mon.display_records()