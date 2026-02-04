#!/bin/bash
set -e#

# Run this script in a python virtual environment

python -m pip install -r requirements.txt

# Build the collector python script into a single executable file with required dependencies
pyinstaller --onefile --distpath ./dist --name nvme_collector --clean --noconfirm nvme_collector.py

# Install the application files
sudo mkdir -p /etc/nvme_collector
sudo mkdir -p /opt/nvme_collector
sudo mkdir -p /var/log/nvme_mon
# The nvme-cli commands need to run as root, but the service is running as user nvme_mon, to keep log files non-root reaable.
# The following code allows the nvme_mon user to run the nvme-cli *read-only* commands as root, without entering a password.
# To revoke this access later, delete /etc/sudoers.d/nvme-mon
NVME_BIN=$(sudo which nvme) && sudo tee /etc/sudoers.d/nvme-mon <<EOF
Cmnd_Alias NVME_SAFE_CMDS = $NVME_BIN smart-log *, \\
                            $NVME_BIN id-ctrl *, \\
                            $NVME_BIN list *, \\
                            $NVME_BIN error-log *, \\
                            $NVME_BIN get-feature *

nvme_mon ALL=(root) NOPASSWD: NVME_SAFE_CMDS
EOF
sudo chmod 0440 /etc/sudoers.d/nvme-mon
sudo systemctl stop nvme_collector.service || true
sudo cp ./dist/nvme_collector /opt/nvme_collector/nvme_collector
sudo ln -sf /opt/nvme_collector/nvme_collector /usr/local/bin/nvme_collector

# Create the service configuration file
sudo tee /etc/nvme_collector/env.conf > /dev/null <<'EOF'
LOG_LEVEL=info
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
ExecStart=/usr/local/bin/nvme_collector
EnvironmentFile=/etc/nvme_collector/env.conf
Restart=always
RestartSec=10
User=nvme_mon
Group=nvme_mon
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable --now nvme_collector.service
sudo systemctl status nvme_collector.service
