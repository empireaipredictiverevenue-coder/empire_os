import sys, os
sys.path.insert(0, "/root/empire_os")
from empire_os.omega_ai_learning_engine import app
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=9100, log_level="info", workers=1)
