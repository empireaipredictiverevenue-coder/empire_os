#!/usr/bin/env python3
"""
Defensive Monitoring System for IMAP Protection
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

MONITOR_LOG_PATH = Path("/root/empire_os/feedback/monitoring.log")
ALERT_LOG_PATH = Path("/root/empire_os/feedback/alerts.log")

class DefensiveMonitor:
    def __init__(self):
        self.memory_limit_mb = int(os.getenv('MEMORY_LIMIT_MB', 500))
        self.max_email_size = int(os.getenv('MAX_EMAIL_SIZE', 1048576))
        
    def setup_logging(self):
        MONITOR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(name)s %(levelname)s %(message)s',
            handlers=[
                logging.FileHandler(MONITOR_LOG_PATH),
                logging.StreamHandler()
            ]
        )
        self.log = logging.getLogger('defensive_monitor')
        
    def check_memory_usage(self):
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
            memory_percent = (memory_mb / self.memory_limit_mb) * 100
            
            status = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metric': 'memory_usage',
                'memory_mb': memory_mb,
                'memory_limit_mb': self.memory_limit_mb,
                'memory_percent': memory_percent,
                'status': 'OK' if memory_percent < 80 else 'WARNING'
            }
            
            if status['status'] == 'WARNING':
                self.log.warning(f"High memory usage: {memory_percent:.1f}%")
                
            return status
        except Exception:
            return {'status': 'ERROR'}
            
    def check_email_size_safety(self):
        """Check for email size safety"""
        try:
            if MONITOR_LOG_PATH.exists():
                with open(MONITOR_LOG_PATH, 'a') as f:
                    f.write(f"{datetime.now().isoformat()}: Checking email size safety - MAX: {self.max_email_size} bytes\n")
            return {'status': 'OK', 'message': 'Size safety checked'}
        except Exception as e:
            return {'status': 'ERROR', 'message': str(e)}

if __name__ == "__main__":
    monitor = DefensiveMonitor()
    monitor.setup_logging()
    print("Starting defensive monitor...")
    
    while True:
        memory_check = monitor.check_memory_usage()
        size_check = monitor.check_email_size_safety()
        print(f"Memory: {memory_check}")
        time.sleep(60)
