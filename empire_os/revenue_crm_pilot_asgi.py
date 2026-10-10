"""ASGI entrypoint: fail startup unless founder pilot authority is valid."""
from empire_os.revenue_crm_pilot_service import build_revenue_crm_pilot_service

app = build_revenue_crm_pilot_service()
