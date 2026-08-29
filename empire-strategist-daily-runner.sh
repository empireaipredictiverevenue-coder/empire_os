[Unit]
Description=Daily Empire Strategist tick (06:00 UTC)
After=empire-hub-8081.service

[Service]
Type=oneshot
WorkingDirectory=/root/empire_os
Environment=PYTHONPATH=/root/empire_os:/root/empire_os/empire_os
ExecStart=/root/venv/bin/python3 /root/empire_os/empire_strategist.py --once
StandardOutput=journal
StandardError=journal
SyslogIdentifier=empire-strategist-daily
