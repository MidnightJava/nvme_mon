sudo systemctl daemon-reload
sudo systemctl stop nvme-mon || true
sudo mkdir -p /opt/nvme_mon
sudo cp -r dist/nvme_mon/* /opt/nvme_mon/
sudo ln -sf /opt/nvme_mon/nvme_mon /usr/local/bin/nvme_mon
sudo chown -R root:root /opt/nvme_mon
sudo chmod -R 755 /opt/nvme_mon
sudo systemctl start nvme-mon
sudo systemctl status nvme-mon
