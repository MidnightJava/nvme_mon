# NVME SSD Monitoring Application

A Linux/Python application that monitors the health of all installed NVME SSDs. The application consists of two components:

- A script that is installed as a Linux service. It periodically collects SMART data from the installed disks and writes it to a log file.

- A python command-line application that reads the log file and displays current disk health info and a historical summary of disk temperatures. It also sends email alert messages when health info values exceed configured thresholds.
  - Run the client in the foreground, OR
  - Run it in headless mode as a service. This provides continuous background disk monitoring, with email alerts

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

### Python Virtual Environment (optional)
* Install [PyEnv](https://github.com/pyenv/pyenv) or any other python virtual environment package
* Commands below work with PyEnv:
```bash
cd nvme-mon
pyenv install 3.14
pyenv virtualenv 3.14 nvme-mon
pyenv activate nvme-mon
```

## SMART Data Collection Service Installation

### Install Monitor/Collection Script
```bash
cd nvme-mon
sudo cp nvme_monitor.py /usr/local/bin/nvme_monitor.py
```

### Create the Service Configuration
```bash
cat << EOF | sudo tee /etc/systemd/system/nmve-monitor.service > /dev/null
[Unit]
Description=NVME SMART Data Collection Daemon
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

### Enable and Start the Collection Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nvme-monitor
```

## Command Line Client

### Install Dependencies
```bash
cd nvme-mon
pyenv activate nvme-mon
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
python -m nvme_mon.app #Show SMART data and temperature histogram
python -m nvme_mon.app headless #No dsplay, useful for providing email alerts only
```
The app will automatically discover all NVME devices and colect SMART statistics for each device every 5 minutes (configurable in nvme_monitor.py). Log entries will be written to */var/log/nvme_health.json* (read by the clent app) and */var/log/nvme_health_readable.log* (text records, with a subset of fields). NB: Use log-rotate or an alternative mechanism to maintain the size of the log files as desired.
- Press the Tab key to cycle through all the devices.
- Press the s key to change the sort column for the histogram. You can sort by temperature, date of the last occurrence of each temperature value, or temperature value counts.
- Press the r key to cyvle through different result scope settings for the histogram. You can view all results, the top 5 results, results for temperature >= 60, and results for temperature >= 70.
- Press the t key to toggle between date and date-time for the Last Occurrence field in the histogram.
- Press the q key to quit.

### Display Features
**Top Section:** Device ID (from /dev/disk/by-id) and the number of days of log info being displayed.

**Disk Health Info:** Current values of SMART data read from the device (refreshed every 60 seconds). The health_score field is a custom calculation intended to give an estimate of disk health, where 100 is perfect and 0 represents catastrophic failure. The algorithm (found in nvme_monitor.py) takes into account the *percent_used*, *media_errors*, *num_err_log_entries*, and *critical_warning* fields.

**Summary Temperature Info:** Min, max, and median temperatures from the current log file. Each temperature entry in the log is an average of the readings from all sensors for each sample. Depending on the SSD, there will be a main temperature reading and readings from zero to eight secondary sensors.

**Temperature Histograms:** Shows the number of records found for each temperature value, and the date and (optionally) time of the last reading for each temperature

### Install and Run the Email Alert Background Service

#### Create a Service User

```bash
sudo useradd \
  --system \
  --home /var/lib/nvme_mon \
  --shell /usr/sbin/nologin \
  nvme_mon
```

#### Install The Configuration and Environment Files
```bash
cd nvme_mon #i.e. ener top-level project directory
sudo mkdir -p /etc/nvme_mon
sudo cp nvme_mon/config.yaml /etc/nvme_mon/config.yaml
sudo vim /etc/nvme_mon/config.yaml #If customization is needed
sudo vim /etc/nvme_mon/nvme_mon.env # or copy .env file if you created one for use as a foreground app
```

#### Install The Runtime State Directory
```bash
# The app will create and manage a .last_alert file here, to keep track of alert history
sudo mkdir -p /var/lib/nvme_mon
sudo chown -R nvme_mon:nvme_mon /var/lib/nvme_mon
sudo chmod 700 /var/lib/nvme_mon
```

#### Create the Service Configuration
```bash
cat << EOF | sudo tee /etc/systemd/system/nmve-monitor.service > /dev/null
[Unit]
Description=NVMe Health Reporting Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=nvme_mon
Group=nvme_mon

ExecStart=/opt/nvme_mon/nvme_mon headless /etc/nvme_mon/config.yaml
WorkingDirectory=/var/lib/nvme_mon

# Load environment variables here
EnvironmentFile=/etc/nvme_mon/nvme_mon.env

Environment=PYTHONUNBUFFERED=1

Restart=on-failure
RestartSec=5

KillSignal=SIGTERM
TimeoutStopSec=30

# Hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/var/lib/nvme_mon

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
```

#### Build the Python App
```cd <top-level project directory>```
```bash
pyinstaller \
  --onedir \
  --name nvme_mon \
  --clean \
  --noconfirm \
  main.py
```

### Deploy the Python App as a Service Binary
```bash
sudo systemctl stop nvme_mon
sudo mkdir -p /opt/nvme_mon
sudo cp -r dist/nvme_mon/* /opt/nvme_mon/
sudo ln -sf /opt/nvme_mon/nvme_mon /usr/local/bin/nvme_mon
sudo chown -R root:root /opt/nvme_mon
sudo chmod -R 755 /opt/nvme_mon
sudo systemctl start nvme_mon
sudo systemctl status nvme_mon
```

### Shortcut Build and Deploy
```cd <top-level project directory>```
```bash
./pybuild.sh && ./deploy.sh
```

#### Enable and Start the Email Alert Service
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now nvme_mon
```

## Overview of Installation Layout

```
/opt/nvme_mon/               ← application
│
├── nvme_mon                 ← executable
├── _internal/
├── lib-dynload/
└── base_library.zip

/etc/nvme_mon/
├── config.yaml              ← app config
└── nvme_mon.env             ← environment variables

/var/lib/nvme_mon/
└── .last_alert              ← runtime state
```



