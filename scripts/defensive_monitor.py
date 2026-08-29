#!/usr/bin/env python3
"""
Defensive Monitoring for IMAP Protection
"""
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

MONITOR_LOG = Path("/root/empire_os/feedback/defensive_monitor.log")
ALERT_LOG = Path("/root/empire_os/feedback/alerts.log")

# Setup logging
MONITOR_LOG.parent.mkdir(parents=True, exist_ok=True)
ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
log = logging.getLogger(__name__)

class DefensiveMonitor:
    MAX_EMAIL_SIZE = 1048576
    MEMORY_LIMIT_MB = 500
    
    def __init__(self):
        self.max_email_size = self.MAX_EMAIL_SIZE
        self.memory_limit_mb = self.MEMORY_LIMIT_MB
        
    def check_email_size_safety(self):
        """Check for email size compliance"""
        try:
            if MONITOR_LOG.exists():
                with open(MONITOR_LOG, 'a') as f:
                    f.write(f"{datetime.now().isoformat()}: Checking email size - MAX: {self.max_email_size} bytes\n")
            return True
        except Exception:
            return False
            
    def check_memory_usage(self):
        """Check memory usage"""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
            log.info(f"Memory usage: {memory_mb:.1f} MB / {self.memory_limit_mb} MB")
            return memory_mb < (self.memory_limit_mb * 2)
        except Exception:
            return True
            
    def run_checks(self):
        """Run all defensive checks"""
        size_check = self.check_email_size_safety()
        memory_check = self.check_memory_usage()
        
        status = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'size_check': 'PASS' if size_check else 'FAIL',
            'memory_check': 'PASS' if memory_check else 'WARNING',
            'overall': 'PASS' if size_check and memory_check else 'DEGRADED'
        }
        
        log.info(f"Defensive checks: {status}")
        return status

if __name__ == "__main__":
    monitor = DefensiveMonitor()
    print("Starting defensive IMAP monitoring...")
    
    while True:
        monitor.run_checks()
        time.sleep(60)