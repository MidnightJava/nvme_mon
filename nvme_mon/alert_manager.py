from datetime import datetime, timedelta
from pytimeparse import parse
from email_sender import send_email
from pathlib import Path
from os import path

from rich_ui import print_debug

LAST_ALERT_FILENAME = ".last_alert"

class AlertManager:

    def __init__(self):
        self.thresholds = {}
        self.config = {}

    def set_config(self, thresholds, settings):
        self.thresholds = thresholds
        self.settings = settings

    def send_alert(self, device_name, health_info):
        lines =[]
        for k,v in self.thresholds.items():
            if k == 'health_score':
                if health_info.get(k) < v:
                    lines.append(f"Alert: {k} below {v}. Value: {health_info.get(k)}")
            else:
                if health_info.get(k) > v:
                    lines.append(f"Alert: {k} exceeds {v}. Value: {health_info.get(k)}")
        if lines:
            send_email(subject=f"SMART Data Alert for Device {device_name}", body="\n".join(lines))

    def check_alerts(self, device_name, health_info):
        last_alert_file = path.join(Path(__file__).parent.resolve(), LAST_ALERT_FILENAME)
        try:
            with open(last_alert_file, "r") as f:
                last_alert_str = f.read().strip()
                last_alert = datetime.strptime(last_alert_str, "%Y-%m-%d %H:%M:%S")
        except FileNotFoundError:
            last_alert = None
        current_time = datetime.now()
        interval = self.settings["alert_interval"]
        alert_interval = timedelta(seconds=parse(interval))
        if last_alert is None or current_time - last_alert > alert_interval:
            self.send_alert(device_name, health_info)
            with open(last_alert_file, "w") as f:
                f.write(current_time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            print_debug("No new alerts to send.")
