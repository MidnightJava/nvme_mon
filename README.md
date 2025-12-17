# NVME SSD Monitoring Application

A python application that monitors the health of all installed NVME SSDs. The application consists of two components: a script that periodically
collects SMART data from the installed disks and writes it to a log file, and a client application that reads the log and displays the current
disk health and a historical summary of disk temperatires. Info for each disk is displayed one page at a time, which you can cycle through using
the tab key. Other keys may be used to change the sort column, scope of the results set, and datetime format of temperature records.

## Dependencies
 # python 3.x (tested with 3.14)
 # linux package nvme-cli
 # python library rich
 
## Installation

### System Package Installation

#### For Ubuntu/Debian users:
```bash
sudo apt update
sudo apt install -y python3-numpy python3-psutil python3-serial python3-evdev
cd led-matrix-monitoring
python3 led_system_monitor.py
```

#### For Fedora users:
```bash
sudo dnf install -y python3-numpy python3-psutil python3-pyserial python3-evdev
cd led-matrix-monitoring
python3 led_system_monitor.py
```

### Python Virtual Environment (optional)
* Install [PyEnv](https://github.com/pyenv/pyenv) or any other python virtual environment package
* Commands below work with PyEnv:
```bash
cd led-matrix-monitoring
pyenv install 3.14
pyenv virtualenv 3.14 nvme-mon
pyenv activate nvme-mon
pip install -r requirements.txt
```
