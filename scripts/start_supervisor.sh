#!/bin/bash

set -e

# Supervisor management script - runs the main supervisor daemon
# This is the primary supervisor that replaced all other supervisor processes

echo "=== Starting Empire Supervisor Daemon ==="

# Run the supervisor daemon - this replaces all other supervisor implementations
# The supervisor_daemon.py monitors all empire-agent-* systemd services and restarts them
# if they crash, providing the core functionality needed for stability

cd /root
/root/venv/bin/python3 scripts/supervisor_daemon.py start
