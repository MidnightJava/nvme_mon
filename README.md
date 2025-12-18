# NVME SSD Monitoring Application

A Linux/Python application that monitors the health of all installed NVME SSDs. The application consists of two components:

- A script that is installed as a Linux service. It periodically collects SMART data from the installed disks and writes it to a log file.

- A python command-line application that reads the log file and displays current disk health info and a historical summary of disk temperatures. Info for each disk is displayed one page at a time, which you can cycle through using the tab key. Other keys may be used to change the sort column, scope, and date-time format of the temperature histogram records.

<img width="1200" height="673" alt="image" src="https://github.com/user-attachments/assets/0ba49e84-82af-4f63-a9fa-e39e1f6c16e9" />

 
## Installation

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

### Python Virtual Environment (optional)
* Install [PyEnv](https://github.com/pyenv/pyenv) or any other python virtual environment package
* Commands below work with PyEnv:
```bash
cd nvme-mon
pyenv install 3.14
pyenv virtualenv 3.14 nvme-mon
pyenv activate nvme-mon
```

### Monitoring Service Installation

#### Install Monitor Script
```bash
cd nvme-mon
sudo cp nvme_monitor.py /usr/local/bin/nvme_monityor.py
```

#### Create Service Configuration
```bash
cat << EOF | sudo tee /etc/systemd/system/nmve-monitor.service > /dev/null
[Unit]
Description=NVMe Health Monitoring Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /usr/local/bin/nvme_monitor.py
Restart=always
RestartSec=10
User=root

[Install]
WantedBy=multi-user.target
EOF
```

#### Enable and Start the Script
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nvme-monitor
```
### Install Client Dependencies
```bash
cd nvme-mon
pyenv activate nvme-mon
pip install -r requireements.txt
```

## Run the Client
```bash
cd nvme-mon
pyenv activate nvme-mon
python nvme_mon/nvme_mon/py
```
The app will automatically discover all NVME devices and colect SMART statistics for each device every 5 minutes (configurable in nvme_monitor.py). Log entries will be written to */var/log/nvme_health.json* (read by the clent app) and */var/log/nvme_health_readable.log* (text records, with a subset of fields). NB: Use log-rotate or an alternative mechanism to maintain the size of the log files as desired.
- Press the Tab key to cycle through all the devices.
- Press the s key to change the sort column for the histogram. You can sort by temperature, date of the last occurrence of each temperature value, or temperature value counts.
- Press the r key to cyvle through different result scope settings for the histogram. You can view all results, the top 5 results, results for temperature >= 60, and results for temperature >= 70.
- Press the t key to toggle between date and date-time for the Last Occurrence field in the histogram.
- Press the q key to quit.

## Display Features
**Top Section:** Device ID (from /dev/disk/by-id) and the number of days of log info being displayed.

**Disk Health Info:** Current values of SMART data read from the device (refreshed every 60 seconds). The health_score field is a custom calculation intended to give an estimate of disk health, where 100 is perfect and 0 represents catastrophic failure. The algorithm (found in nvme_monitor.py) takes into account the *percent_used*, *media_errors*, *num_err_log_entries*, and *critical_warning* fields.

**Summary Temperature Info:** Min, max, and median temperatures from the current log file. Each temperature entry in the log is an average of the readings from all sensors for each sample. Depending on the SSD, there will be a main temperature reading and readings from zero to eight secondary sensors.

**Temperature Histograms:** Shows the number of records found for each temperature value, and the date and (optionally) time of the last reading for each temperature



