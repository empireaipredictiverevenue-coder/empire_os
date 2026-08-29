#cloud-config
package_update: true
package_upgrade: true
packages:
  - python3
  - python3-pip
  - python3-venv
  - postgresql-15
  - redis-server
  - curl
  - git
  - build-essential
  - libpq-dev
  - python3-dev

write_files:
  - path: /root/empire_os/.env
    owner: root:root
    permissions: '0600'
    content: |
      EMPIRE_DB_PATH=/root/empire_os/empire_os.db
      EMPIRE_CORE_API_KEY={{empire_core_key}}
      POSTGRES_PASSWORD={{postgres_password}}
      REDIS_PASSWORD={{redis_password}}
      REGION={{region}}
      METROS={{metros}}
      BSC_RPC_URL=https://bsc-dataseed.binance.org
      BSC_USDT_CONTRACT=0x55d398326f99059fF775485246999027B3197955
      BSC_WALLET_ADDRESS=0x1339b487046B0ad924a10c20b1791608EA8595a8

  - path: /root/empire_os/empire_os/empire_os.db
    owner: root:root
    permissions: '0644'
    encoding: base64
    content: {{db_base64}}

runcmd:
  # Setup PostgreSQL
  - systemctl enable postgresql
  - systemctl start postgresql
  - sleep 5
  - sudo -u postgres psql -c "CREATE USER empire WITH PASSWORD '${POSTGRES_PASSWORD}';"
  - sudo -u postgres psql -c "CREATE DATABASE empire_os OWNER empire;"
  - sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE empire_os TO empire;"
  
  # Setup Redis
  - sed -i 's/^# requirepass .*/requirepass '${REDIS_PASSWORD}'/' /etc/redis/redis.conf
  - sed -i 's/^bind 127.0.0.1 ::1/bind 0.0.0.0/' /etc/redis/redis.conf
  - systemctl enable redis-server
  - systemctl restart redis-server
  
  # Clone Empire OS
  - cd /root && git clone https://github.com/empire-os/empire_os.git || true
  - cd /root/empire_os && pip3 install -r requirements.txt || true
  
  # Initialize PostgreSQL schema
  - cd /root/empire_os && python3 -c "
import psycopg2
conn = psycopg2.connect(
    host='localhost',
    database='empire_os',
    user='empire',
    password='${POSTGRES_PASSWORD}'
)
cur = conn.cursor()
# Run schema from infra/sql/postgres-schema.sql
with open('/root/empire_os/infra/sql/postgres-schema.sql') as f:
    cur.execute(f.read())
conn.commit()
" || true
  
  # Setup Empire OS systemd service
  - cat > /etc/systemd/system/empire-hub.service << 'EOF'
[Unit]
Description=Empire OS Regional Hub
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/empire_os
Environment=EMPIRE_DB_PATH=/root/empire_os/empire_os.db
Environment=POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
Environment=REDIS_PASSWORD=${REDIS_PASSWORD}
Environment=REGION={{region}}
Environment=METROS={{metros}}
ExecStart=/root/venv/bin/python3 -m uvicorn empire_os.hub:app --host 0.0.0.0 --port 8081
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

  - systemctl daemon-reload
  - systemctl enable empire-hub
  - systemctl start empire-hub
  
  # Verify
  - sleep 10
  - curl -sf http://localhost:8081/health || exit 1

final_message: "Empire OS Regional Hub {{region}} deployed successfully!"