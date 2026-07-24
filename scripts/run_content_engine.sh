#!/bin/bash
set +e
incus exec empire-hub -- \
  bash -lc "export OPENROUTER_API_KEY=\$(cat /root/empire_secrets/openrouter_api_key) && cd /root/empire_os && /root/venv/bin/python3 -m empire_os.agents.content_engine"
