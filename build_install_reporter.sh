#!/bin/bash
set -e
# Run this script in a python virtual environment

############################################################################
#                    Before runnning the script                            #
############################################################################
# cp .env.example .env                                                     #
# Edit .env and provide your email server settings and credentials         #
############################################################################

python -m pip install -r requirements.txt
# Build the collector python script into a directory coontaining s single executable,
# required dependencies, and supporting files
pyinstaller \
  --onedir \
  --name nvme_reporter \
  --clean \
  --noconfirm \
  main.py

# Create a service account
if ! id -u "nvme_reporter" &>/dev/null 2>&1; then
  sudo useradd --system --home /var/lib/nvme_reporter --shell /usr/sbin/nologin nvme_reporter
fi

# Install the application files
sudo systemctl stop nvme-reporter.service || true
sudo mkdir -p /opt/nvme_reporter
sudo systemctl stop nvme_reporter.service || true
sudo cp -r dist/nvme_reporter/* /opt/nvme_reporter/
sudo ln -sf /opt/nvme_reporter/nvme_reporter /usr/local/bin/nvme_reporter
sudo chown -R root:root /opt/nvme_reporter
sudo chmod -R 755 /opt/nvme_reporter

# Install the configuration and environment files
sudo mkdir -p /etc/nvme_reporter
sudo cp nvme_mon/config.yaml /etc/nvme_reporter/config.yaml
sudo cp .env /etc/nvme_reporter/env.conf

# Install the runtime state directory, where the app maintains a .last_alert file,
# to keep track of alert history
sudo mkdir -p /var/lib/nvme_reporter
sudo chown -R nvme_reporter:nvme_reporter /var/lib/nvme_reporter
sudo chmod 700 /var/lib/nvme_reporter

# Create the service configuration
sudo tee /etc/systemd/system/nvme_reporter.service > /dev/null << 'EOF'
[Unit]
Description=NVMe Health Reporting Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=nvme_reporter
Group=nvme_reporter

ExecStart=/opt/nvme_reporter/nvme_reporter headless /etc/nvme_reporter/config.yaml
WorkingDirectory=/var/lib/nvme_reporter

# Load environment variables here
EnvironmentFile=/etc/nvme_reporter/env.conf
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
ReadWritePaths=/var/lib/nvme_reporter

StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start the service
sudo systemctl daemon-reload
sudo systemctl enable --now nvme_reporter.service
sudo systemctl status nvme_reporter.service