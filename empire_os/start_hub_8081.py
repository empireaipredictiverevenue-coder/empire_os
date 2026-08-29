#!/usr/bin/env python3
import os
os.environ["EMPIRE_PORT"] = "8081"
os.environ["EMPIRE_HOST"] = "0.0.0.0"
import uvicorn
from empire_os.hub import app
uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")