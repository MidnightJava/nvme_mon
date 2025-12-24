from datetime import datetime, timedelta
from pytimeparse import parse
from pathlib import Path
from os import path
from collections import defaultdict
import json
import logging

from nvme_mon.email_sender import EmailSender
from nvme_mon.paths import app_data_path

log = logging.getLogger(__name__)

LAST_ALERT_FILENAME = ".last_alert"

history_record = lambda: {"last_value": None, "timestamp": None}

compare_func = {
    "num_err_log_entries": lambda val, threshold: val > threshold,
    "unsafe_shutdowns": lambda val, threshold: val > threshold,
    "percentage_used": lambda val, threshold: val > threshold,
    "media_errors": lambda val, threshold: val > threshold,
    "health_score": lambda val, threshold: val < threshold,
    "mean_temperature": lambda val, threshold: val > threshold
}

class AlertManager:

    def __init__(self, config_file):
        self.config_file = config_file
        self.thresholds = {}
        self.config = {}

    def set_config(self, thresholds, settings):
        self.thresholds = thresholds
        self.settings = settings

    def send_alert(self, device_name, health_info):
        current_time = datetime.now()
        interval = self.settings["alert_interval"]
        alert_interval = timedelta(seconds=parse(interval))
        lines =[]
        try:
            with open(app_data_path(LAST_ALERT_FILENAME), "r") as f:
                history = defaultdict(lambda: defaultdict(history_record), json.load(f))
        except FileNotFoundError:
                history = defaultdict(lambda: defaultdict(history_record))
        for k,v in health_info.items():
            if k in compare_func and compare_func[k](v, self.thresholds[k]):
                log.debug(f'Considering alert for {k}')
                last_alert = history[device_name][k]["timestamp"]
                if last_alert is not None:
                    last_alert_time = datetime.strptime(last_alert, "%Y-%m-%d %H:%M:%S")
                else:
                    last_alert_time = None
                # Include the alert if it's the first one for this field, or if the last alert was sent more than the
                # configured interval ago, or if the current value further exceeds the threshold than it did in the last alert.
                if last_alert_time is None or (datetime.now() - last_alert_time).total_seconds() > alert_interval.total_seconds() \
                        or (k in history[device_name] and compare_func[k](v, history[device_name][k]["last_value"])):
                    lines.append(f"{k} = {v}. Configured threshold is {self.thresholds[k]}.")
                    history[device_name][k]["last_value"] = v
                    history[device_name][k]["timestamp"] = current_time.strftime("%Y-%m-%d %H:%M:%S")
        if lines:
            lines.insert(0, f"The following SMART data values are beyond their configured threshold:\n")
            lines.append(f"\nDevice: {device_name}")
            log.debug('Calling send_email')
            try:
                EmailSender().send_email(subject=f"SMART Data Alert for Device {device_name}", body="\n".join(lines))
                with open(app_data_path(LAST_ALERT_FILENAME), "w") as f:
                    json.dump(history, f)
            except Exception as e:
                log.info(f"Error sending email: {e}")