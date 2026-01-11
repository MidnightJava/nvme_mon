python -m pip install -r requirements.txt
pyinstaller \
  --onedir \
  --name nvme_mon \
  --clean \
  --noconfirm \
  main.py
