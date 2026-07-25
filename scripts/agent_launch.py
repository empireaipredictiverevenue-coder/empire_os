#!/usr/bin/env python3
"""
Empire Agent Launcher - Start all revenue + intelligence agents as background daemons
Set up rate-limit scheduling for production stability
"""
import subprocess
import time
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path

class AgentLauncher:
    def __init__(self):
        self.agents = [
            # Revenue agents
            {
                "name": "lead_sniper",
                "script": "/root/empire_os/scripts/lead_sniper_agent.py",
                "priority": "high",
                "rate_limit": 60,  # Check every 60 seconds
                "description": "AI-powered lead intelligence and sales automation"
            },
            {
                "name": "marketplace",
                "script": "/root/empire_os/scripts/marketplace_agent.py", 
                "priority": "high",
                "rate_limit": 120,  # Check every 2 minutes
                "description": "B2B lead marketplace and buyer coordination"
            },
            {
                "name": "buyer_hunter",
                "script": "/root/empire_os/scripts/buyer_hunter_agent.py",
                "priority": "medium", 
                "rate_limit": 180,  # Check every 3 minutes
                "description": "Automated B2B buyer identification and outreach"
            },
            {
                "name": "seller_platform",
                "script": "/root/empire_os/scripts/seller_platform_agent.py",
                "priority": "medium",
                "rate_limit": 240,  # Check every 4 minutes
                "description": "Seller platform management and service coordination"
            },
            {
                "name": "revenue",
                "script": "/root/empire_os/scripts/revenue_agent.py",
                "priority": "high", 
                "rate_limit": 90,  # Check every 90 seconds
                "description": "Revenue tracking and pipeline management"
            },
            {
                "name": "finance",
                "script": "/root/empire_os/scripts/finance_agent.py",
                "priority": "high",
                "rate_limit": 300,  # Check every 5 minutes
                "description": "Financial tracking and payout processing"
            },
            {
                "name": "billing",
                "script": "/root/empire_os/scripts/billing_agent.py", 
                "priority": "medium",
                "rate_limit": 180,
                "description": "Automated billing and invoice processing"
            },
            {
                "name": "paypal",
                "script": "/root/empire_os/scripts/paypal_agent.py",
                "priority": "medium",
                "rate_limit": 240,
                "description": "PayPal integration and payment processing"
            },
            {
                "name": "crypto_charge",
                "script": "/root/empire_os/scripts/crypto_charge.py",
                "priority": "medium", 
                "rate_limit": 120,
                "description": "Cryptocurrency payment processing"
            },
            {
                "name": "settlement_gateway",
                "script": "/root/empire_os/scripts/settlement_gateway.py",
                "priority": "high",
                "rate_limit": 60,
                "description": "Settlement gateway and payment coordination"
            },
            {
                "name": "payout",
                "script": "/root/empire_os/scripts/payout.py",
                "priority": "medium",
                "rate_limit": 180,
                "description": "Automated payout processing and distribution"
            },
            {
                "name": "payout_batch",
                "script": "/root/empire_os/scripts/payout_batch.py",
                "priority": "medium",
                "rate_limit": 300,
                "description": "Batch payout processing for efficiency"
            },
            {
                "name": "solana_listener",
                "script": "/root/empire_os/scripts/solana_listener.py",
                "priority": "high",
                "rate_limit": 90,
                "description": "Solana blockchain listener for real-time transactions"
            },
            
            # Intelligence agents
            {
                "name": "neural_scout", 
                "script": "/root/empire_os/scripts/neural_scout.py",
                "priority": "high",
                "rate_limit": 60,
                "description": "Cortex intelligence neural scout for market analysis"
            },
            {
                "name": "scout_intel",
                "script": "/root/empire_os/scripts/scout_intel.py",
                "priority": "high",
                "rate_limit": 60,
                "description": "Scout intelligence gathering and market monitoring"
            },
            {
                "name": "predictive",
                "script": "/root/empire_os/scripts/predictive_agent.py",
                "priority": "medium",
                "rate_limit": 120,
                "description": "Predictive revenue modeling and forecasting"
            },
            {
                "name": "crawler",
                "script": "/root/empire_os/scripts/crawler_agent.py",
                "priority": "medium",
                "rate_limit": 180,
                "description": "Automated web crawling for lead generation"
            },
            {
                "name": "sim",
                "script": "/root/empire_os/scripts/simulation_agent.py",
                "priority": "low",
                "rate_limit": 300,
                "description": "Pattern simulation and scenario modeling"
            },
            {
                "name": "deep_research",
                "script": "/root/empire_os/scripts/deep_research_agent.py",
                "priority": "low",
                "rate_limit": 600,
                "description": "Deep research and academic paper analysis"
            },
        ]
        
        self.running_agents = {}
        self.lock = threading.Lock()
        self.log_file = Path("/root/feedback/agent_launcher.log")
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
    
    def log(self, level, msg, **fields):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "process": "agent_launcher",
            "msg": msg,
            **fields
        }
        with open(self.log_file, "a") as f:
            f.write(f"{entry}\n")
        print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] LAUNCHER {level}: {msg}")
    
    def start_agent(self, agent_config):
        agent_name = agent_config["name"]
        script_path = agent_config["script"]
        
        self.log("INFO", f"Starting agent {agent_name}", name=agent_name, script=script_path)
        
        try:
            # Start agent as background process
            process = subprocess.Popen(
                ["/root/venv/bin/python3", script_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            with self.lock:
                self.running_agents[agent_name] = {
                    "process": process,
                    "pid": process.pid,
                    "config": agent_config,
                    "start_time": datetime.now(timezone.utc),
                    "last_check": datetime.now(timezone.utc)
                }
            
            self.log("INFO", f"Agent {agent_name} started (PID: {process.pid})", 
                       name=agent_name, pid=process.pid)
            return True
            
        except Exception as e:
            self.log("ERROR", f"Failed to start agent {agent_name}: {e}", 
                       name=agent_name, error=str(e))
            return False
    
    def check_agent_health(self, agent_name):
        with self.lock:
            if agent_name not in self.running_agents:
                return False
            
            agent_info = self.running_agents[agent_name]
            process = agent_info["process"]
            
            # Check if process is still running
            if process.poll() is not None:
                self.log("WARN", f"Agent {agent_name} has terminated (exit code: {process.returncode})", 
                           name=agent_name, exit_code=process.returncode)
                del self.running_agents[agent_name]
                return False
            
            # Update last check time
            agent_info["last_check"] = datetime.now(timezone.utc)
            return True
    
    def monitor_agents(self):
        self.log("INFO", "Starting agent health monitoring")
        
        while True:
            try:
                # Check all running agents
                to_restart = []
                for agent_name in list(self.running_agents.keys()):
                    if not self.check_agent_health(agent_name):
                        to_restart.append(agent_name)
                
                # Restart failed agents
                for agent_name in to_restart:
                    self.log("INFO", f"Restarting failed agent {agent_name}", name=agent_name)
                    
                    # Get agent config
                    if agent_name in self.running_agents:
                        agent_config = self.running_agents[agent_name]["config"]
                        success = self.start_agent(agent_config)
                        if success:
                            self.log("INFO", f"Successfully restarted agent {agent_name}", name=agent_name)
                        else:
                            self.log("ERROR", f"Failed to restart agent {agent_name}", name=agent_name)
                
                time.sleep(30)  # Check every 30 seconds
                
            except KeyboardInterrupt:
                self.log("INFO", "Agent launcher shutting down")
                break
            except Exception as e:
                self.log("ERROR", f"Agent monitor error: {e}")
                time.sleep(60)
    
    def cleanup_agents(self):
        self.log("INFO", "Cleaning up all running agents")
        
        with self.lock:
            for agent_name, agent_info in list(self.running_agents.items()):
                process = agent_info["process"]
                try:
                    process.terminate()
                    process.wait(timeout=10)
                    self.log("INFO", f"Terminated agent {agent_name}", name=agent_name)
                except Exception as e:
                    try:
                        process.kill()
                        self.log("WARN", f"Force killed agent {agent_name}", name=agent_name, error=str(e))
                    except:
                        self.log("ERROR", f"Failed to kill agent {agent_name}", name=agent_name)
        
        self.running_agents.clear()
    
    def run(self):
        self.log("INFO", "Starting Empire Agent Launcher")
        self.log("INFO", f"Configured {len(self.agents)} agents", count=len(self.agents))
        
        # Show summary of agents to start
        high_priority = [a for a in self.agents if a["priority"] == "high"]
        medium_priority = [a for a in self.agents if a["priority"] == "medium"]
        low_priority = [a for a in self.agents if a["priority"] == "low"]
        
        self.log("INFO", f"Agent distribution - High: {len(high_priority)}, Medium: {len(medium_priority)}, Low: {len(low_priority)}")
        
        # Start all agents
        started_count = 0
        for agent_config in self.agents:
            success = self.start_agent(agent_config)
            if success:
                started_count += 1
                # Rate limit start times to prevent overwhelming
                time.sleep(1)
        
        self.log("INFO", f"Started {started_count}/{len(self.agents)} agents successfully")
        
        if started_count == 0:
            self.log("ERROR", "Failed to start any agents")
            return
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=self.monitor_agents, daemon=True)
        monitor_thread.start()
        
        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.log("INFO", "Received shutdown signal")
        
        self.cleanup_agents()
        self.log("INFO", "Agent launcher stopped")

if __name__ == "__main__":
    launcher = AgentLauncher()
    launcher.run()
