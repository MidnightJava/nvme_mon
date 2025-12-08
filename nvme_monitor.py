#!/usr/bin/env python3
import glob
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime
from statistics import mean

LOG_JSON = "/var/log/nvme_health.json"
LOG_HUMAN = "/var/log/nvme_health_readable.log"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"



# -----------------------------
# Logging Setup
# -----------------------------
def setup_logging():
    os.makedirs("/var/log", exist_ok=True)

    # Main namespace logger
    root_logger = logging.getLogger("nvme_monitor")
    root_logger.setLevel(logging.INFO)
    root_logger.propagate = False

    # Strip handlers if systemd already added a journald handler
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # JSON handler
    json_handler = logging.FileHandler(LOG_JSON)
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(logging.Formatter("%(message)s"))

    # Human readable handler
    human_handler = logging.FileHandler(LOG_HUMAN)
    human_handler.setLevel(logging.INFO)
    human_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))

    # Console handler (systemd)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))

    # Attach console to the main logger
    root_logger.addHandler(console_handler)

    # Sub-loggers for JSON and human-readable
    json_logger = logging.getLogger("nvme_monitor.json")
    json_logger.setLevel(logging.INFO)
    json_logger.propagate = False
    json_logger.addHandler(json_handler)

    human_logger = logging.getLogger("nvme_monitor.human")
    human_logger.setLevel(logging.INFO)
    human_logger.propagate = False
    human_logger.addHandler(human_handler)

    return json_logger, human_logger, root_logger


json_logger, human_logger, root_logger = setup_logging()


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
        root_logger.error(f"Failed to run {' '.join(cmd)}: {e}")
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
def monitor(interval=60):
    root_logger.info("NVMe monitoring daemon starting...")

    while True:
        devices = discover_nvme_devices()

        if not devices:
            root_logger.warning("No NVMe devices found.")
        else:
            root_logger.info(f"Discovered devices: {devices}")

        for dev in devices:
            idc = read_id_ctrl(dev)
            smart = read_smart(dev)

            health = extract_health(dev, idc, smart)
            if not health:
                root_logger.error(f"Failed to extract health for {dev}")
                continue

            # Write JSON
            json_logger.info(json.dumps(health))

            # Write human log
            human_logger.info(
                f"{dev}: {health['temperature_c']:.1f}°C, "
                f"{health['percentage_used']}% used, "
                f"{health['media_errors']} media errors "
                f"health score: {health['health_score']}"
            )

        time.sleep(interval)


if __name__ == "__main__":
    monitor()
#!/usr/bin/env python3
import glob
import json
import logging
import os
import re
import subprocess
import time
from datetime import datetime


LOG_JSON = "/var/log/nvme_health.jsonl"
LOG_HUMAN = "/var/log/nvme_health_readable.log"


# -----------------------------
# Logging Setup
# -----------------------------
def setup_logging():
    os.makedirs("/var/log", exist_ok=True)

    # Main namespace logger
    root_logger = logging.getLogger("nvme_monitor")
    root_logger.setLevel(logging.INFO)
    root_logger.propagate = False

    # Strip handlers if systemd already added a journald handler
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # JSON handler
    json_handler = logging.FileHandler(LOG_JSON)
    json_handler.setLevel(logging.INFO)
    json_handler.setFormatter(logging.Formatter("%(message)s"))

    # Human readable handler
    human_handler = logging.FileHandler(LOG_HUMAN)
    human_handler.setLevel(logging.INFO)
    human_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))

    # Console handler (systemd)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))

    # Attach console to the main logger
    root_logger.addHandler(console_handler)

    # Sub-loggers for JSON and human-readable
    json_logger = logging.getLogger("nvme_monitor.json")
    json_logger.setLevel(logging.INFO)
    json_logger.propagate = False
    json_logger.addHandler(json_handler)

    human_logger = logging.getLogger("nvme_monitor.human")
    human_logger.setLevel(logging.INFO)
    human_logger.propagate = False
    human_logger.addHandler(human_handler)

    return json_logger, human_logger, root_logger


json_logger, human_logger, root_logger = setup_logging()


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
        root_logger.error(f"Failed to run {' '.join(cmd)}: {e}")
        return None


def read_smart(device_path):
    """Read SMART log for a device."""
    return run_nvme_json(["smart-log", device_path])


def read_id_ctrl(device_path):
    """Read NVMe Identify Controller log."""
    return run_nvme_json(["id-ctrl", device_path])


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
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "device": device,
        "temperature_k": smart.get("temperature"),
        "temperature_c": smart.get("temperature") - 273.15 if smart.get("temperature") else None,
        "sensor_1_c": smart.get("temp_sensor_1"),
        "sensor_2_c": smart.get("temp_sensor_2"),
        "power_on_hours": smart.get("power_on_hours"),
        "unsafe_shutdowns": smart.get("unsafe_shutdowns"),
        "media_errors": smart.get("media_errors"),
        "num_err_log_entries": smart.get("num_err_log_entries"),
        "percentage_used": smart.get("percentage_used"),
    }

    return entry


# -----------------------------
# Monitoring Loop
# -----------------------------
def monitor(interval=60):
    root_logger.info("NVMe monitoring daemon starting...")

    while True:
        devices = discover_nvme_devices()

        if not devices:
            root_logger.warning("No NVMe devices found.")
        else:
            root_logger.info(f"Discovered devices: {devices}")

        for dev in devices:
            idc = read_id_ctrl(dev)
            smart = read_smart(dev)

            health = extract_health(dev, idc, smart)
            if not health:
                root_logger.error(f"Failed to extract health for {dev}")
                continue

            # Write JSON
            json_logger.info(json.dumps(health))

            # Write human log
            human_logger.info(
                f"{dev}: {health['temperature_c']:.1f}°C, "
                f"{health['percentage_used']}% used, "
                f"{health['media_errors']} media errors"
            )

        time.sleep(interval)


if __name__ == "__main__":
    monitor()
