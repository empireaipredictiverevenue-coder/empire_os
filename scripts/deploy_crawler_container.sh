#!/bin/bash
set -e

CONTAINER="empire-crawler"
IMAGE="ubuntu/jammy/cloud"

echo "=== Creating Incus profile for crawler ==="
incus profile create empire-crawler 2>/dev/null || true
cat << 'PROF' | incus profile edit empire-crawler
config:
  environment.HTTP_PROXY: http://10.118.155.1:8118
  environment.HTTPS_PROXY: http://10.118.155.1:8118
  environment.NO_PROXY: 127.0.0.1,localhost,10.118.155.0/24,::1
  limits.cpu: "2"
  limits.memory: 2GiB
  boot.autostart: "true"
description: "Empire OS Crawler Agent"
devices:
  eth0:
    name: eth0
    network: empire-net
    type: nic
  root:
    path: /
    pool: default
    size: 10GiB
    type: disk
PROF

echo "=== Launching crawler container ==="
if ! incus list --format csv | grep -q "^${CONTAINER},"; then
    incus launch ubuntu/jammy/cloud ${CONTAINER} -p empire-crawler -p default
    echo "Waiting for container to be ready..."
    sleep 10
    incus exec ${CONTAINER} -- bash -c "
        apt-get update -qq && apt-get install -y -qq python3 python3-pip curl jq sqlite3 2>&1 | tail -3
        pip3 install -q requests beautifulsoup4 lxml 2>&1 | tail -1
    "
fi

echo "=== Copying crawler code ==="
incus file create -p ${CONTAINER}/root/empire_os/ -d
for f in crawler_runner.py scrape_contractors.py lead_intake.py; do
    [ -f "/root/empire_os/empire_os/$f" ] && incus file push /root/empire_os/empire_os/$f ${CONTAINER}/root/empire_os/
done

echo "=== Creating systemd service inside container ==="
incus exec ${CONTAINER} -- bash -c "
cat > /etc/systemd/system/empire-crawler.service << 'UNIT'
[Unit]
Description=Empire OS Lead Crawler
After=network-online.target

[Service]
Type=exec
User=root
WorkingDirectory=/root/empire_os
ExecStart=/usr/bin/python3 -m crawler_runner
Restart=always
RestartSec=30
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable empire-crawler.service
systemctl start empire-crawler.service
"

echo "=== Status ==="
incus exec ${CONTAINER} -- systemctl status empire-crawler.service --no-pager 2>&1 | head -5
echo ""
echo "Container: ${CONTAINER}"
echo "To attach: incus exec ${CONTAINER} bash"
