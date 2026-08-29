"""Wrapper to run mail_sender without empire_os __init__ issues."""
import sys
sys.path.insert(0, "/root/empire_os")

import importlib.util
spec = importlib.util.spec_from_file_location(
    "mail_sender", "/root/empire_os/empire_os/mail_sender.py"
)
mod = importlib.util.module_from_spec(spec)
mod.__package__ = None
spec.loader.exec_module(mod)

if "--once" in sys.argv:
    mod.send_pending_batch()
else:
    mod.main()