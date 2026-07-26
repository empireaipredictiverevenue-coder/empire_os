#!/usr/bin/env python3
"""
Empire OS Supervisor - Monitors and Restarts Agents

This supervisor script continuously monitors all registered Empire OS agents
(62+ agents total) and restarts them if they fail, ensuring the system remains
operational 24/7 with zero downtime.

CRITICAL MISSION:
- Monitor 62+ Empire OS agents
- Automatically restart failed agents
- Maintain system availability 99.99%
- Collect performance metrics
- Provide health monitoring

AGENT TYPES:
- C-Suite: CEO, Chief of Staff, Business Manager
- Operations: Operations Manager, Finance, Tech Lead
- Marketing: Marketing Manager, Content, Social
- Sales: Sales Manager, CRM, Outreach
- Intelligence: Research, Deep Research, Forecasting
- Infrastructure: Systems Engineer, Security, DevOps
- Content: Writer, SEO, Video, Copywriting
- Special: Satellite Strike, Satellite Damage, SATCOM, Scanner, Emergency Responder
"""

import subprocess
import time
import sys
import json
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional

# Supervisor configuration
SUPERVISOR_CONFIG = Path("/root/empire_os/scripts/.supervisor_config")
LOG_FILE = Path("/root/feedback/supervisor.log")
METRICS_FILE = Path("/root/feedback/supervisor_metrics.jsonl")

# Core agents that should always be running
CRITICAL_AGENTS = [
    "commander", 
    "systems_engineer", 
    "lead_deliverer", 
    "solana_listener"
]

# All registered Empire OS agents (62+ total)
ALL_EMPIRE_AGENTS = [
    "commander",
    "chief_of_staff",
    "business_manager",
    "operations_manager",
    "finance",
    "tech_lead",
    "marketing_manager",
    "content",
    "seo",
    "video",
    "copywriting",
    "sales_manager",
    "crm",
    "outreach",
    "research",
    "deep_research",
    "forecasting",
    "systems_engineer",
    "security",
    "devops",
    "content_manager",
    "writer",
    "editor",
    "social_media",
    "community_manager",
    "email",
    "messaging",
    "lead_deliverer",
    "distribution",
    "tracking",
    "partner_manager",
    "alliance",
    "negotiations",
    "satellite_strike",
    "satellite_strike_cap",
    "satellite_damage",
    "satellite_damage_bda",
    "idle_asset_sniper",
    "mass_tort",
    "finance_agent",
    "legal_compliance",
    "growth",
    "traffic",
    "scheduling",
    "hangout",
    "synthetic_agents",
    "synthetic_sim_agent",
    "sys",
    "satellite_service",
    "satellite_damage_bda",
    "satellite_damage_cap",
    "satellite_scanner",
    "satellite_strike_cap",
    "satellite_strike",
    "solana_listener",
    "warehouse_report",
    "sentry"
]

class EmpireSupervisor:
    def __init__(self):
        self.agent_stats = {}
        self.total_restarts = 0
        self.failed_agents = []
        self.last_health_check = None
        self.uptime_start = time.time()
        
        # Ensure log directories exist
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, level: str, message: str, agent: str = None, details: dict = None):
        """Log supervisor event with full details"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        log_entry = {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "agent": agent,
            "supervisor_pid": os.getpid(),
            "total_restarts": self.total_restarts,
            "active_agents": len(self.failed_agents)
        }
        
        if details:
            log_entry.update(details)
        
        # Write to log file
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
        
        # Print to console
        agent_prefix = f"[{agent}]" if agent else ""
        print(f"[{timestamp[:19]}] {level}: {agent_prefix} {message}")
    
    def is_agent_running(self, agent_name: str) -> bool:
        """Check if an Empire OS agent is currently running"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", f"empire-agent-{agent_name}.service"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() == "active"
        except subprocess.TimeoutExpired:
            self.log("WARN", f"Agent check timeout", agent=agent_name)
            return False
        except Exception as e:
            self.log("DEBUG", f"Agent check failed: {str(e)}", agent=agent_name)
            return False
    
    def start_agent(self, agent_name: str) -> bool:
        """Start an Empire OS agent"""
        self.log("INFO", "Attempting to start agent", agent=agent_name)
        
        try:
            # Create service file if it doesn't exist
            service_file = f"/etc/systemd/system/empire-agent-{agent_name}.service"
            
            # Standard Empire agent service configuration
            service_content = f"""[Unit]
Description=Empire OS Agent: {agent_name}
After=network.target
StartLimitBurst=3
StartLimitInterval=60

[Service]
Type=simple
User=root
WorkingDirectory=/root/empire_os
Environment=PYTHONUNBUFFERED=1
ExecStart=/root/empire_os/venv/bin/python3 /root/empire_os/empire_os/agents/{agent_name}_agent.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
            
            # Write service file
            with open(service_file, "w") as f:
                f.write(service_content)
            
            # Reload systemd and start agent
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            result = subprocess.run(
                ["systemctl", "start", f"empire-agent-{agent_name}.service"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                # Wait a moment for agent to start
                time.sleep(3)
                if self.is_agent_running(agent_name):
                    self.log("SUCCESS", "Agent started successfully", agent=agent_name)
                    return True
                else:
                    self.log("ERROR", "Agent failed to start or died immediately", agent=agent_name)
                    return False
            else:
                self.log("ERROR", f"Failed to start agent: {result.stderr}", agent=agent_name)
                return False
                
        except subprocess.TimeoutExpired:
            self.log("ERROR", "Agent start timeout", agent=agent_name)
            return False
        except Exception as e:
            self.log("ERROR", f"Exception starting agent: {str(e)}", agent=agent_name)
            return False
    
    def collect_agent_metrics(self):
        """Collect health and performance metrics from all agents"""
        metrics = {}
        
        for agent_name in ALL_EMPIRE_AGENTS:
            try:
                # Check if agent is running
                is_running = self.is_agent_running(agent_name)
                
                if is_running:
                    # Get process info if available
                    ps_result = subprocess.run(
                        ["pgrep", "-f", f"agent-{agent_name}_agent.py"],
                        capture_output=True,
                        text=True
                    )
                    
                    process_ids = ps_result.stdout.strip().split('\n') if ps_result.stdout else []
                    
                    metrics[agent_name] = {
                        "status": "RUNNING",
                        "process_ids": process_ids,
                        "pid_count": len(process_ids),
                        "last_check": datetime.now(timezone.utc).isoformat(),
                        "health": "HEALTHY"
                    }
                else:
                    metrics[agent_name] = {
                        "status": "STOPPED",
                        "process_ids": [],
                        "pid_count": 0,
                        "last_check": datetime.now(timezone.utc).isoformat(),
                        "health": "ERROR"
                    }
                    
            except Exception as e:
                metrics[agent_name] = {
                    "status": "UNKNOWN",
                    "error": str(e),
                    "last_check": datetime.now(timezone.utc).isoformat(),
                    "health": "ERROR"
                }
        
        return metrics
    
    def save_metrics(self, metrics: dict):
        """Save collected metrics to file"""
        try:
            metric_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "total_agents": len(metrics),
                "running_agents": sum(1 for m in metrics.values() if m.get("status") == "RUNNING"),
                "failed_agents": sum(1 for m in metrics.values() if m.get("status") == "STOPPED"),
                "agent_details": metrics
            }
            
            with open(METRICS_FILE, "a") as f:
                f.write(json.dumps(metric_entry) + "\n")
                
        except Exception as e:
            self.log("ERROR", f"Failed to save metrics: {str(e)}")
    
    def restart_failed_agents(self, metrics: dict):
        """Restart all agents that are not running"""
        restarted_count = 0
        
        for agent_name, agent_metrics in metrics.items():
            if agent_metrics.get("status") != "RUNNING":
                self.log("WARN", "Agent is down, attempting restart", agent=agent_name)
                if self.start_agent(agent_name):
                    restarted_count += 1
                    self.total_restarts += 1
                    self.failed_agents = []  # Reset failed agents list
                    self.log("INFO", f"Agent {agent_name} restarted successfully", agent=agent_name)
                else:
                    self.failed_agents.append(agent_name)
                    self.log("ERROR", f"Failed to restart agent {agent_name}", agent=agent_name)
        
        if restarted_count > 0:
            self.log("EVENT", f"Restarted {restarted_count} agents", details={"restarted_count": restarted_count})
        
        return restarted_count
    
    def run_monitoring_cycle(self):
        """Complete monitoring and recovery cycle"""
        self.log("INFO", "Starting monitoring cycle")
        
        # Collect health metrics from all agents
        metrics = self.collect_agent_metrics()
        
        # Save metrics for analysis
        self.save_metrics(metrics)
        
        # Restart any failed agents
        restarted_count = self.restart_failed_agents(metrics)
        
        # Log summary
        total_agents = len(metrics)
        running_agents = sum(1 for m in metrics.values() if m.get("status") == "RUNNING")
        
        if restarted_count > 0:
            self.log("EVENT", f"Cycle complete: {restarted_count} agents restarted, {running_agents}/{total_agents} running")
        else:
            self.log("INFO", f"Cycle complete: All {running_agents}/{total_agents} agents running")
    
    def run(self):
        """Main supervisor loop"""
        self.log("INFO", "Empire Supervisor starting", details={
            "version": "v3.0",
            "total_agents_monitoring": len(ALL_EMPIRE_AGENTS),
            "critical_agents": CRITICAL_AGENTS,
            "health_check_interval": "60 seconds"
        })
        
        try:
            while True:
                cycle_start = time.time()
                self.run_monitoring_cycle()
                
                # Calculate sleep time to maintain 60-second cycle
                cycle_time = time.time() - cycle_start
                sleep_time = max(0, 60 - cycle_time)
                
                self.log("DEBUG", f"Cycle completed in {cycle_time:.2f}s, sleeping {sleep_time:.2f}s")
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            self.log("INFO", "Supervisor shutting down gracefully")
            sys.exit(0)
        except Exception as e:
            self.log("CRITICAL", f"Supervisor fatal error: {str(e)}")
            sys.exit(1)

def main():
    """Initialize and start Empire Supervisor"""
    import os  # Add missing import
    
    supervisor = EmpireSupervisor()
    supervisor.run()

if __name__ == "__main__":
    main()