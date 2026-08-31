#!/bin/bash
set -e
incus exec empire-hub -- \
  bash -lc "export GROQ_API_KEY=$(cat /root/empire_secrets/groq_api_key) export PATH=\"/root/venv/bin:$PATH\" && cd /root/empire_os && /root/venv/bin/python3 -m empire_os.agents.content_engine"
