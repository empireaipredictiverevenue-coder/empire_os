#0 */6 * * * /root/venv/bin/python3 /root/empire_os/scripts/bulk_insert_phase1.py >> /root/empire_os/logs/redeliver_phase1.log 2>&1
#0 2 * * 0 /root/venv/bin/python3 /root/empire_os/scripts/bulk_insert_phase2.py >> /root/empire_os/logs/redeliver_phase2.log 2>&1
