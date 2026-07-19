import sys
sys.path.insert(0, "/root/empire_os")
from mcp.server.fastmcp import FastMCP
import inspect
print("INIT SIG:", inspect.signature(FastMCP.__init__))
try:
    m = FastMCP("empire_mcp", host="0.0.0.0", port=8082)
    print("settings:", m.settings)
except Exception as e:
    print("err:", e)
