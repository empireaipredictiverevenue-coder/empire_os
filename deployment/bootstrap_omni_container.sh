#!/bin/bash
# Bootstrap the Empire AI Node Omni-Agent inside the empire-omni-agent Incus container.
# Run on host AFTER `incus launch debian/12 empire-omni-agent --network empire-net` finishes.
set -e
CT=empire-omni-agent
APP=/opt/empire-omni-agent

echo "[bootstrap] waiting for container network..."
for i in $(seq 1 30); do
  IP=$(incus list $CT --format csv | awk -F, '/RUNNING/{print $4; exit}')
  [ -n "$IP" ] && break
  sleep 2
done
echo "[bootstrap] container IP: $IP"

# install node + redis client deps inside container
incus exec $CT -- bash -c "apt-get update -qq && apt-get install -y -qq curl ca-certificates gnupg >/dev/null 2>&1; curl -fsSL https://deb.nodesource.com/setup_22.x | bash - >/dev/null 2>&1; apt-get install -y -qq nodejs >/dev/null 2>&1; node --version"

# push agent files
incus file push /root/empire_os/empire_os/market_agent_node.js $CT$APP/market_agent_node.js 2>/dev/null || {
  incus exec $CT -- mkdir -p $APP
  incus file push /root/empire_os/empire_os/market_agent_node.js $CT$APP/market_agent_node.js
  incus file push /root/empire_os/empire_os/package.json $CT$APP/package.json
}

# npm install inside container
incus exec $CT -- bash -c "cd $APP && npm install --no-audit --no-fund >/dev/null 2>&1 && echo npm_ok"

# ensure redis reachable on empire-net (host redis listens on 6379; container uses host bridge IP)
REDIS_HOST=$(incus network get empire-net ipv4.address | cut -d/ -f1)
echo "[bootstrap] empire-net gateway: $REDIS_HOST"

# write systemd unit inside container
incus exec $CT -- bash -c "cat > /etc/systemd/system/empire-omni-agent.service <<EOF
[Unit]
Description=Empire AI Node Omni-Agent (7-module market engine)
After=network.target
[Service]
Type=simple
WorkingDirectory=$APP
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=REDIS_URL=redis://$REDIS_HOST:6379
ExecStart=/usr/bin/node $APP/market_agent_node.js
Restart=always
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload && systemctl enable empire-omni-agent && systemctl start empire-omni-agent"
echo "[bootstrap] done. status:"
incus exec $CT -- systemctl is-active empire-omni-agent || true
