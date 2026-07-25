#!/usr/bin/env python3
"""
Fixed intelligence_loop - connection pooling to prevent DB lock errors.
This version uses proper connection handling and avoids concurrent writes.
"""
import sqlite3
import time
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
import signal
import sys

# Global configuration
DB_PATH = Path("/root/empire_os/data/intelligence.db")
LOG_FILE = Path("/root/feedback/intelligence_loop.jsonl")

# Connection pooling configuration
MAX_CONNECTIONS = 3

# Agent task priorities
TASK_PRIORITIES = {
    "neural_scout": 1,      # High - Cortex controller
    "scout_intel": 2,        # High - 60s scan intervals  
    "predictive": 3,         # Medium - Revenue predictions
    "crawler": 4,            # Medium - Lead extraction
    "sim": 5,                # Low - Pattern simulation
    "deep_research": 6,      # Low - Research papers
}

class ConnectionPool:
    """Connection pool to manage database connections and prevent DB lock errors"""
    def __init__(self, max_connections=MAX_CONNECTIONS):
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
    
    def get_connection(self):
        """Get a database connection from the pool"""
        with self.lock:
            # Try to get an existing idle connection
            for i, conn in enumerate(self.connections):
                if conn['idle']:
                    conn['idle'] = False
                    conn['last_used'] = datetime.now(timezone.utc)
                    return conn['connection']
            
            # If we need a new connection, create one (if under limit)
            if len(self.connections) < self.max_connections:
                conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON")
                
                self.connections.append({
                    'connection': conn,
                    'idle': False,
                    'created': datetime.now(timezone.utc),
                    'last_used': datetime.now(timezone.utc)
                })
                return conn
            
            # Otherwise, wait for a connection to become available
            # This prevents overwhelming the database
            time.sleep(0.1)
            return self.get_connection()
    
    def release_connection(self, conn):
        """Release a connection back to the pool"""
        with self.lock:
            for conn_info in self.connections:
                if conn_info['connection'] == conn:
                    conn_info['idle'] = True
                    conn_info['last_used'] = datetime.now(timezone.utc)
                    break

class TaskQueue:
    """Priority task queue for agent tasks"""
    def __init__(self):
        self.queue = Queue()
        self.task_lock = threading.Lock()
    
    def enqueue_task(self, agent_name, task_data):
        """Add a task to the queue"""
        with self.task_lock:
            priority = TASK_PRIORITIES.get(agent_name, 999)
            self.queue.put((priority, time.time(), agent_name, task_data))
    
    def dequeue_task(self):
        """Get a task from the queue or return None if empty"""
        try:
            priority, timestamp, agent, data = self.queue.get_nowait()
            return agent, data
        except:
            return None, None

class IntelligenceLoop:
    """Main intelligence loop with thread-safe database operations"""
    def __init__(self):
        self.running = True
        self.connection_pool = ConnectionPool()
        self.task_queue = TaskQueue()
        self.log_file = LOG_FILE
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        self.log("INFO", f"Intelligence loop received signal {signum}, shutting down")
        self.running = False
    
    def _ensure_db_directory(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, level, msg, **fields):
        """Log messages with timestamp and level"""
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "loop": "intelligence",
            "msg": msg,
            **fields
        }
        with open(self.log_file, "a") as f:
            f.write(f"{json.dumps(entry)}\n")
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] INTEL {level}: {msg}")
    
    def _safe_db_operation(self, operation, *args, **kwargs):
        """Execute DB operations safely with connection pooling"""
        conn = self.connection_pool.get_connection()
        try:
            return operation(conn, *args, **kwargs)
        finally:
            self.connection_pool.release_connection(conn)
    
    def _init_db_schema(self):
        """Initialize database schema if not exists"""
        def create_schema(conn):
            conn.execute("BEGIN")
            
            # Core intelligence data table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intelligence_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_type TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    priority INTEGER DEFAULT 0,
                    last_scan TIMESTAMP,
                    status TEXT DEFAULT 'active',
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_type ON intelligence_sources(source_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sources_priority ON intelligence_sources(priority)")
            
            # Scan results table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scan_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id INTEGER,
                    scan_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'completed',
                    result_data TEXT,
                    FOREIGN KEY (source_id) REFERENCES intelligence_sources(id),
                    INDEX idx_scan_source (source_id),
                    INDEX idx_scan_type (scan_type)
                )
            """)
            
            conn.execute("COMMIT")
        
        try:
            self._safe_db_operation(create_schema)
            self.log("INFO", "Database schema initialized")
        except Exception as e:
            self.log("ERROR", f"Failed to initialize database schema: {e}")
    
    def _test_connection(self):
        """Test database connection"""
        def test_conn(conn):
            conn.execute("SELECT 1")
        
        try:
            self._safe_db_operation(test_conn)
            return True
        except Exception as e:
            self.log("ERROR", f"Database connection test failed: {e}")
            return False
    
    def _cleanup_old_data(self):
        """Clean up old scan results to prevent database bloat"""
        def cleanup(conn):
            cursor = conn.cursor()
            
            # Delete old results (older than 7 days)
            cursor.execute("""
                DELETE FROM scan_results 
                WHERE timestamp < datetime('now', '-7 days')
            """)
            
            # Return count of deleted records
            cursor.execute("""
                SELECT COUNT(*) as deleted_count
                FROM scan_results 
                WHERE timestamp < datetime('now', '-7 days')
            """)
            
            return cursor.fetchone()[0]
        
        try:
            deleted_count = self._safe_db_operation(cleanup)
            if deleted_count > 0:
                self.log("INFO", f"Cleaned up {deleted_count} old scan results")
        except Exception as e:
            self.log("ERROR", f"Failed to cleanup old data: {e}")
    
    def _save_scan_result(self, source_id, scan_type, result_data):
        """Save scan results with exclusive lock to prevent concurrent writes"""
        def save_result(conn):
            cursor = conn.cursor()
            
            # Use exclusive transaction to prevent concurrent writes to same table
            cursor.execute("BEGIN EXCLUSIVE")
            
            cursor.execute("""
                INSERT INTO scan_results (source_id, scan_type, status, result_data)
                VALUES (?, ?, ?, ?)
            """, (source_id, scan_type, "completed", json.dumps(result_data)))
            
            conn.commit()
            return cursor.lastrowid
        
        try:
            result_id = self._safe_db_operation(save_result)
            self.log("INFO", f"Scan result saved, id: {result_id}")
            return result_id
        except Exception as e:
            self.log("ERROR", f"Failed to save scan result: {e}")
            return None
    
    def _run_source_scan(self, source_id, source_config):
        """Execute a scan for a specific intelligence source"""
        self.log("INFO", f"Starting scan for source {source_id}", 
                   source_id=source_id, source_type=source_config.get('type'))
        
        # Prepare scan results
        scan_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source_id': source_id,
            'results': [],
            'metrics': {
                'success_rate': 0.95,
                'data_points': 100,
                'scan_duration': 2.5
            }
        }
        
        # Simulate processing time
        time.sleep(1)
        
        # Save results safely
        result_id = self._save_scan_result(source_id, source_config['type'], scan_data)
        
        if result_id:
            self.log("INFO", f"Scan completed for source {source_id}, result_id: {result_id}", 
                       source_id=source_id, result_id=result_id)
        else:
            self.log("ERROR", f"Scan failed for source {source_id}", source_id=source_id)
        
        return result_id
    
    def _add_standard_tasks(self):
        # Add standard tasks - neural_scout for cortex controller
        # Priority 1 - high priority for neural scouting
        self.task_queue.enqueue_task("neural_scout", {"name": "neural_scout", "type": "neural_scanner", "priority": 1})
        
        # Add scout_intel for scouting intelligence
        # Priority 2 - high priority for scout intelligence gathering
        self.task_queue.enqueue_task("scout_intel", {"name": "scout_intel", "type": "scout_scanner", "priority": 2})
        
        # Add predictive for revenue predictions
        # Priority 3 - medium priority for predictive modeling
        self.task_queue.enqueue_task("predictive", {"name": "predictive", "type": "predictive_scanner", "priority": 3})
        
        # Add crawler for web scraping
        # Priority 4 - medium priority for data crawling
        self.task_queue.enqueue_task("crawler", {"name": "crawler", "type": "web_crawler", "priority": 4})
        
        # Add sim for simulation tasks
        # Priority 5 - low priority for pattern simulation
        self.task_queue.enqueue_task("sim", {"name": "sim", "type": "pattern_simulator", "priority": 5})
        
        # Add deep_research for deep research
        # Priority 6 - low priority for research papers
        self.task_queue.enqueue_task("deep_research", {"name": "deep_research", "type": "deep_researcher", "priority": 6})
    
    def _process_tasks(self):
        """Process up to 10 tasks from the task queue"""
        tasks_processed = 0
        for _ in range(10):
            agent, task_data = self.task_queue.dequeue_task()
            if agent and task_data:
                tasks_processed += 1
                source_id = task_data.get('name', f"source_{int(time.time())}")
                self._run_source_scan(task_data.get('name'), task_data)
            else:
                break
        return tasks_processed
    
    def run(self):
        """Main intelligence loop execution"""
        self.log("INFO", "Intelligence loop started")
        self._ensure_db_directory()
        
        # Initialize database
        self._init_db_schema()
        
        # Test database connection
        if not self._test_connection():
            self.log("ERROR", "Database connection test failed, exiting")
            return
        
        # Add initial tasks
        self._add_standard_tasks()
        
        # Main processing loop
        cycle_count = 0
        while self.running:
            try:
                cycle_count += 1
                self.log("INFO", f"Intelligence loop cycle {cycle_count}")
                
                # Cleanup old data periodically
                if cycle_count % 10 == 0:
                    self._cleanup_old_data()
                
                # Process tasks
                tasks_processed = self._process_tasks()
                
                self.log("INFO", f"Cycle {cycle_count} complete, processed {tasks_processed} tasks", 
                           cycle=cycle_count, tasks_processed=tasks_processed)
                
                # Wait before next cycle
                time.sleep(30)
                
            except KeyboardInterrupt:
                self.log("INFO", "Intelligence loop interrupted by user")
                break
            except Exception as e:
                self.log("ERROR", f"Intelligence loop error in cycle {cycle_count}: {e}", 
                           cycle=cycle_count, error=str(e))
                time.sleep(30)
        
        self.log("INFO", "Intelligence loop stopped")

def main():
    loop = IntelligenceLoop()
    loop.run()

if __name__ == "__main__":
    main()
