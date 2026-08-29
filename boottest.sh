#!/bin/bash
pkill -9 -f "empire_os.hub" 2>/dev/null
sleep 2
/root/venv/bin/python3 -m empire_os.hub --host 127.0.0.1 --port 8082 > /tmp/hub_boot.log 2>&1 &
echo "boottest pid $!" > /tmp/boottest_pid.log
sleep 20
echo "=== after 20s ===" >> /tmp/hub_boot.log
curl -sf -m 3 http://127.0.0.1:8082/health >> /tmp/hub_boot.log 2>&1 && echo " UP" >> /tmp/hub_boot.log || echo " DOWN" >> /tmp/hub_boot.log
