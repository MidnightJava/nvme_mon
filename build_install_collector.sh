#!/bin/bash
set -e#

# Run this script in a python virtual environment

python -m pip install -r requirements.txt

# Build the collector python script into a single executable file with required dependencies
pyinstaller --onefile --distpath ./dist --name nvme_collector --clean --noconfirm nvme_collector.py

if [[ $? -ne 0 ]]; then
    echo "ERROR: Failed to build nvme_collector"
    exit 1
fi

# Install the application files
sudo mkdir -p /etc/nvme_collector
sudo mkdir -p /opt/nvme_collector
sudo mkdir -p /var/log/nvme_mon
# The nvme-cli commands need to be run as root, but the service is running as user nvme_mon, to keep log files
# readable by the nvme_reporter user (for the resporter service). To do this, we create udev rules to set group
# ownership of the nvme devices to nvme_mon, and create a restricted copy of the nvme binary that is group-owned
# by nvme_mon, so that the collector can run the nvme commands it needs without running the entire service as root

# Create udev rules
sudo tee /etc/udev/rules.d/99-nvme.rules <<EOF
# NVMe controller char devices
SUBSYSTEM=="nvme", KERNEL=="nvme[0-9]*", GROUP="nvme_mon", MODE="0660"

# NVMe namespace block devices
SUBSYSTEM=="block", KERNEL=="nvme[0-9]*n[0-9]*", GROUP="nvme_mon", MODE="0660"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger

# Create a restricted binary.
sudo cp $(which nvme) /usr/local/bin/nvme_mon_cli
sudo chown root:nvme_mon /usr/local/bin/nvme_mon_cli
sudo chmod 750 /usr/local/bin/nvme_mon_cli
sudo setcap cap_sys_admin+ep /usr/local/bin/nvme_mon_cli

# Ensure the archive log file exists and is owned by the nvme_mon user, since the collector will prune old records from this file
sudo touch /var/log/nvme_mon/log_archive.json
sudo chown nvme_mon:nvme_mon /var/log/nvme_mon/log_archive.json
sudo chmod 660 /var/log/nvme_mon/log_archive.json

# Install the collector binary
sudo systemctl stop nvme_collector.service || true
sudo cp ./dist/nvme_collector /opt/nvme_collector/nvme_collector
sudo ln -sf /opt/nvme_collector/nvme_collector /usr/local/bin/nvme_collector

# Create the service configuration file
sudo tee /etc/nvme_collector/env.conf > /dev/null <<'EOF'
LOG_LEVEL=debug
# Number of seconds between data collections
COLLECTION_INTERVAL=300
MAX_RECORD_AGE=30 days
# One day
ARCHIVE_INTERVAL=86400
EOF

sudo tee /etc/systemd/system/nvme_collector.service > /dev/null <<'EOF'
[Unit]
Description=NVME SMART Data Collection Daemon
After=network.target

[Service]
Type=simple
# ExecStart=/usr/local/bin/nvme_collector
ExecStart=/usr/bin/unbuffer /usr/local/bin/nvme_collector
EnvironmentFile=/etc/nvme_collector/env.conf
Environment="RUNNING_UNDER_SYSTEMD=1"
Restart=always
RestartSec=10
User=nvme_mon
Group=nvme_mon

[Install]
WantedBy=multi-user.target
EOF

Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable --now nvme_collector.service
sudo systemctl status nvme_collector.service
