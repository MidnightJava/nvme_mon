#!/usr/bin/env python3
import glob
import json
import logging
import os
import re
import subprocess
import time
import pwd, grp
import tempfile
from datetime import datetime, timedelta
from pytimeparse import parse
from statistics import mean

LOG_DIR = "/var/log/nvme_mon"

LOG_JSON = os.path.join(LOG_DIR, "nvme_health.json")
LOG_HUMAN = os.path.join(LOG_DIR, "nvme_health_readable.log")
LOG_JSON_ARCHIVE = os.path.join(LOG_DIR, "log_archive.json")
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
DEFAULT_COLLECTION_INTERVAL = 5 * 60  # 5 minutes
COLLECTION_INTERVAL = int(os.environ.get("COLLECTION_INTERVAL", DEFAULT_COLLECTION_INTERVAL))
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

MAX_RECORD_AGE = ""
DEFAULT_ARCHIVE_INTERVAL = 60 * 60 * 24  # 1 day
ARCHIVE_INTERVAL_SEC =int(os.environ.get("ARCHIVE_INTERVAL", DEFAULT_ARCHIVE_INTERVAL))

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
}

log_level = LOG_LEVELS[os.environ.get("LOG_LEVEL", "warning").lower()]
# -----------------------------
# Logging Setup
# -----------------------------
def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    os.chown(LOG_DIR, uid=pwd.getpwnam("root").pw_uid, gid=grp.getgrnam("nvme_mon").gr_gid)
    os.chmod(LOG_DIR, 0o777)

    # Main namespace logger
    root_logger = logging.getLogger("nvme_monitor")
    root_logger.setLevel(log_level)
    root_logger.propagate = False

    # Strip handlers if systemd already added a journald handler
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Console handler (systemd)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))

    # Attach console to the main logger
    root_logger.addHandler(console_handler)
    return root_logger

log = setup_logging()

# -----------------------------
# NVMe Discovery
# -----------------------------
NVME_NAMESPACE_RE = re.compile(r"^nvme\d+n\d+$")

def discover_nvme_devices():
    """
    Discover NVMe namespaces via /dev/disk/by-id with rules:
        • skip all '-partN' files
        • resolve to actual nvmeXnY device
        • only keep one symlink per namespace (shortest name)
    """
    candidates = sorted(glob.glob("/dev/disk/by-id/nvme-*"))
    namespaces = {}

    for path in candidates:
        name = os.path.basename(path)

        # Skip partitions
        if "-part" in name:
            continue

        try:
            target = os.path.realpath(path)
        except OSError:
            continue

        base = os.path.basename(target)

        if not NVME_NAMESPACE_RE.match(base):
            continue  # not a namespace, ignore

        # Deduplicate: choose the shortest symlink string
        if base not in namespaces or len(name) < len(os.path.basename(namespaces[base])):
            namespaces[base] = path

    return sorted(namespaces.values())


# -----------------------------
# NVMe SMART/Log parsing
# -----------------------------
def run_nvme_json(args):
    """
    Run an nvme CLI command and parse json output.
    args: list like ["id-ctrl", "/dev/..."]
    """
    cmd = ["nvme"] + args + ["-o", "json"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception as e:
        log.error(f"Failed to run {' '.join(cmd)}: {e}")
        return None


def read_smart(device_path):
    """Read SMART log for a device."""
    return run_nvme_json(["smart-log", device_path])


def read_id_ctrl(device_path):
    """Read NVMe Identify Controller log."""
    return run_nvme_json(["id-ctrl", device_path])

def health_score(smart) -> int:
        """
        Compute a simple 0–100 health score.
        100 = perfect,   0 = catastrophic failure
        """
        score = 100

        # percentage_used
        if smart.get("percent_used") is not None:
            if smart.get("percent_used") >= 100:
                score -= 60
            else:
                score -= min(smart.get("percent_used") * 0.6, 60)

        # media errors
        if smart.get("media_errors"):
            score -= min(smart.get("media_errors") * 2, 40)

        # controller error log
        if smart.get("num_err_log_entries"):
            score -= min(smart.get("num_err_log_entries") * 0.5, 20)

        # critical warnings
        if smart.get("critical_warning") and smart.get("critical_warning") != 0:
            score -= 30

        # Clamp score
        return max(0, min(int(score), 100))


# -----------------------------
# Health Data Extraction
# -----------------------------
def extract_health(device, id_ctrl, smart):
    """
    Combine id-ctrl and smart-log JSON into a unified health record.
    """
    if not smart:
        return None

    entry = {
        "timestamp": datetime.strftime(datetime.now(), DATE_FORMAT),
        "device": device,
        "temperature_k": smart.get("temperature"),
        "temperature_c": int(smart.get("temperature") - 273.15) if smart.get("temperature") else None,
        "sensor_1_c": smart.get("temp_sensor_1"),
        "sensor_2_c": smart.get("temp_sensor_2"),
        "power_on_hours": smart.get("power_on_hours"),
        "unsafe_shutdowns": smart.get("unsafe_shutdowns"),
        "media_errors": smart.get("media_errors"),
        "num_err_log_entries": smart.get("num_err_log_entries"),
        "percentage_used": smart.get("percent_used"),
        "health_score": health_score(smart)
    }

    temps = []
    if smart.get("temperature"):
        entry["temperature_k"] = int(smart.get("temperature"))
        temp_c = int(smart.get("temperature") - 273.15)
        entry["temperature_c"] = temp_c
        temps.append(temp_c)

    for i in range(1, 9):
        if smart.get(f"temperature_sensor_{i}"):
            temp = int(smart.get(f"temperature_sensor_{i}") - 273.15)
            entry[f"sensor_{i}_c"] = temp
            temps.append(temp)

    entry["mean_temperature"] = int(mean(temps)) if temps else None

    return entry


# -----------------------------
# Monitoring Loop
# -----------------------------
def monitor(interval=COLLECTION_INTERVAL):
    log.info("NVMe monitoring daemon starting...")

    while True:
        devices = discover_nvme_devices()

        if not devices:
            log.warning("No NVMe devices found.")
        else:
            log.debug(f"Discovered devices: {devices}")

        for dev in devices:
            idc = read_id_ctrl(dev)
            smart = read_smart(dev)

            health = extract_health(dev, idc, smart)
            if not health:
                log.error(f"Failed to extract health for {dev}")
                continue

            # Write JSON
            with open(LOG_JSON, "a") as json_log_file:
                json_log_file.write(json.dumps(health) + "\n")

            # Write human log
            with open(LOG_HUMAN, "a") as human_log_file:
                human_log_file.write(
                    f"{dev}: {health['temperature_c']:.1f}°C, "
                    f"{health['percentage_used']}% used, "
                    f"{health['media_errors']} media errors "
                    f"health score: {health['health_score']}"
                    "\n"
                )

        time.sleep(interval)

from threading import Timer

def repeat_function(interval, func, *args, **kwargs):
    def wrapper():
        func(*args, **kwargs)
        Timer(interval, wrapper).start()
    Timer(interval, wrapper).start()

def prune_log_file():
    log.debug("Pruning log file...")
    count = 0
    with tempfile.NamedTemporaryFile(mode="w+t") as temp:
        with open(LOG_JSON, "r") as in_file:
            with open(LOG_JSON_ARCHIVE, "a") as archive:
                for line in in_file:
                    obj = json.loads(line)
                    date_time = datetime.strptime(obj['timestamp'], DATE_FORMAT)
                    max_age = timedelta(seconds=parse(MAX_RECORD_AGE))
                    if (datetime.now() - date_time).total_seconds() > max_age.total_seconds():
                        count += 1
                        archive.write(line)
                    else:
                        temp.write(line)
        if count > 0:
            try:
                os.rename(temp.name, LOG_JSON)
                log.info(f"Wrote {count} old records to archive.")
            except PermissionError:
                log.error(f"Permission denied while archiving file {LOG_JSON}")

if __name__ == "__main__":
    log.debug("Starting NVMe Monitor...")
    repeat_function(ARCHIVE_INTERVAL_SEC, prune_log_file)   
    monitor()

