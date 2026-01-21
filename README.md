# NVME SSD Monitoring Application

A Linux/Python application that monitors the health of all installed NVME SSDs. The application consists of two components:

- **SMART Data Collection Service**:  A python script that is installed as a systemd service. It periodically collects SMART data from the installed disks and writes the data records to a log file.

- **Command Line Client**: A python application that reads the SMART data log file and displays current disk health info and a historical summary of disk temperatures. It also **sends email alert messages** when health info values exceed configured thresholds.
  - Run the client in the **foreground**, OR
  - Run it in headless mode as **a service**. This provides continuous background disk monitoring, with email alerts

<img width="1200" height="673" alt="image" src="https://github.com/user-attachments/assets/0ba49e84-82af-4f63-a9fa-e39e1f6c16e9" />

 
## Install Dependencies

### System Package Installation

#### For Ubuntu/Debian users:
```bash
sudo apt update
sudo apt install nvme-cli
```

#### For Fedora users:
```bash
sudo dnf update
sudo dnf install nvme-cli
```

### Python Virtual Environment (for [PEP 668](https://peps.python.org/pep-0668/) compatibility)
* Install [PyEnv](https://github.com/pyenv/pyenv) or any other python virtual environment package
* Commands below work with PyEnv:
```bash
cd nvme-mon
pyenv install 3.14
pyenv virtualenv 3.14 nvme-mon
pyenv activate nvme-mon
```

## SMART Data Collection Service

### Install and Run the NVME Collector
Run the command below in a python virtual environment.
```
./build_install_collector.sh
```
This script compiles the SMART data collector into a single executable file and installs it as a systemd service. Modify environment variables in the script as desired, for collection interval and management of the collection log files.

**Service Config File**: /etc/systemd/system/nvme_collector.service

**Service Executable**: /usr/local/bin/nvme_collector (sym link pointing to /opt/nvme_collector/nvme_collector)

**Environment File**: /etc/nvme_collector/env.conf

**Service Management**: sudo systemctl enable|start|stop|status nvme_collector

The service runs as root, which is required to invoke the nvme-cli API.

### SMART Data Logs
**Log Directory**: /var/log/nvme_mon

**nvme_health.json**: SMART data records written at the configured collection interval (env var COLLECTION_INTERVAL). The command line client and the Email Alert service read this file. The file is periodically pruned to remove and archive old records, as explained below.

**nvme_health_readable.log**: Human-readable log written at the configured interval, containing a subset of the fields written to the json file. Records from this file are NOT archived.

**log_archive.json**: At the configured archive interval (env var ARCHIVE_INTERVAL), the `nvme_health.json` file is trimmed in accordance with the configured maximum record age (env var MAX_RECORD_AGE). Possibile variable values are defined by the [pytimeparse](https://pypi.org/project/pytimeparse/) library. (e.g, 30d, 5w, 6m). Old records removed from `nvme_health.json` are appended to `log_archive.json`.

**Log Pruning**: The `nvme_health.json` file is pruned to provide a reasonable data set for the command line client. Since the `nvme_health_readable.log` and `log_archive.json` files are not pruned and may grow arbitrarily large, a log rotation scheme should be implemented for these files, for example using the [logrotate](https://linux.die.net/man/8/logrotate) Linux capability.

## Command Line Client

### Install Dependencies
```bash
cd nvme-mon
pyenv activate nvme-mon #or some other virtual env
pip install -r requireements.txt
```

### Run the Client in the Foreground
```bash
cd nvme-mon
pyenv activate nvme-mon
# Skip .env file configuration if email notification is not desired.
cp .env.example .env
# Add/modify values as needed
vim .env
# Edit config if desired
vim nvme_mon/config.yaml
python -m nvme_mon.app #Show SMART data summary and temperature histogram
python -m nvme_mon.app headless #No dsplay, useful for providing email alerts only
```
The app will automatically discover all NVME devices and update the SMART data summary and the temperature histogram for each device every 5 minutes (configurable in app.py). It reads log entries written to `/var/log/nvme_health.json` by the SMART Data Collection Service.
- Press the **Tab** key to cycle through all the devices.
- Press the **s** key to change the sort column for the histogram. You can sort by temperature, date of the last occurrence of each temperature value, or temperature value counts.
- Press the **r** key to cycle through different result scope settings for the histogram. You can view all results, the top 5 results, results for temperature >= 60, or results for temperature >= 70.
- Press the **t** key to toggle between date and date-time for the Last Occurrence field in the histogram.
- Press the **e** key to send a test email.
- Press the **q** key to quit.

### Display Features
**Top Section:** Device ID (from /dev/disk/by-id) and the number of days of log info being displayed.

**Disk Health Info:** Current values of SMART data read from the device. The health_score field is a custom calculation intended to give an estimate of disk health, where 100 is perfect and 0 represents catastrophic failure. The algorithm (found in nvme_collector.py) takes into account the `percent_used`, `media_errors`, `num_err_log_entries`, and `critical_warning` fields.

**Summary Temperature Info:** Min, max, and median temperatures from the current log file. Each temperature entry in the log is an average of the readings from all sensors for that sample. Depending on the SSD, there will be a main temperature reading and readings from zero to eight secondary sensors.

**Temperature Histogram:** Shows the number of records found for each temperature value, and the date and (optionally) time of the last reading for each temperature.

### Install and Run the EMail Alert Service
```
cp .env.example .env
# Enter your email server settings and credentials
vim .env
```

Run the command below in a python virtual environment.
```
./build_install_reporter.sh
```
This script compiles the EMAil reporter into a single executable file and installs it, along with its dependencies ans supporting files, as a systemd service.

**Service Config File**: /etc/systemd/system/nvme_reporter.service

**Service Executable**: /usr/local/bin/nvme_reporter (sym link pointing to /opt/nvme_collector/nvme_reporter)

**Environment File**: /etc/nvme_reporter/env.conf

**Service Management**: sudo systemctl enable|start|stop|status nvme_reporter

The service runs under the system account nvme_reporter, which has no login shell

## Overview of Installation Layout
Collector Service
```
/opt/nvme_collector/               ← application
│
├── nvme_collector                 ← executable

/etc/nvme_collector/
└── env.conf             ← environment variables
```

EMail ALert Service
```
/opt/nvme_reporter/               ← application
│
├── nvme_reporter                 ← executable
├── _internal/

/etc/nvme_reporter/
├── config.yaml              ← app config
└── env.conf             ← environment variables

/var/lib/nvme_reporter/
└── .last_alert              ← runtime state
```



