"""Overlay existing private CRM: append only three reviewed GET routes.

No duplicate login, tenant, database, CRM or work queue.
"""
from pathlib import Path
import sys

PREVIOUS = Path("/opt/empire-ai/crm-search-additive-20261109")
if (not PREVIOUS.is_dir() or PREVIOUS.is_symlink()
        or not (PREVIOUS/"crm_search_additive_20261109/entrypoint.py").is_file()):
    raise RuntimeError("original CRM source release missing")
sys.path.insert(0,str(PREVIOUS))
from crm_search_additive_20261109.entrypoint import app, resolver
from .mount import attach_multi_pipeline_board

attach_multi_pipeline_board(app, resolver)
