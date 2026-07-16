import os
import sys
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# Enable test mode: skips the AGI Loop on hub startup so TestClient
# lifespan shutdown doesn't hang on in-flight LLM calls.
os.environ["EMPIRE_OS_TEST_MODE"] = "1"