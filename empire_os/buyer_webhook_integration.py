"""
Utility function to add buyer webhook endpoints to Empire OS Hub.
This module provides CRM webhook integrations and endpoint routing
for the buyer marketplace webhook service.
"""

from fastapi import FastAPI
from empire_os.buyer_marketplace_webhooks import (
    webhook_manager,
    setup_crm_webhooks,
    CRM_PROVIDER_MAP
)

def add_buyer_webhook_support(app: FastAPI, hub_base_url: str = None) -> None:
    """
    Add buyer webhook support to the Empire OS Hub FastAPI application.
    
    This function:
    1. Configures the webhook manager with Hub's base URL
    2. Sets up CRM webhook endpoints
    3. Adds integration functions for lead processing
    
    Args:
        app: FastAPI application instance
        hub_base_url: Base URL for the Hub (defaults to http://127.0.0.1:8081)
    """
    if hub_base_url is None:
        hub_base_url = "http://127.0.0.1:8081"
    
    # Update webhook manager with Hub URL
    webhook_manager.HUB_URL = hub_base_url.rstrip("/")
    
    # Set up CRM webhook endpoints and integrations
    setup_crm_webhooks(app, webhook_manager)
    
    # Add webhook-related routes to Hub
    @app.get("/v1/buyer-marketplace-webhooks/health")
    async def webhook_health():
        """Webhook service health check."""
        return await webhook_manager.health_check()
    
    @app.post("/v1/buyer-marketplace-webhooks/lead")
    async def forward_marketplace_lead(request):
        """
        Forward lead from marketplace to buyer webhooks.
        
        This endpoint receives leads from the marketplace and forwards them
        to the appropriate buyer CRM webhook service.
        """
        try:
            payload = await request.json()
            return await webhook_manager.receive_lead(request, None)
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    @app.get("/v1/buyer-marketplace-webhooks/dead-letter")
    async def get_dead_letter_queue(limit: int = 100):
        """Get dead letter queue entries."""
        return await webhook_manager.get_dead_letter_queue(limit)

# Export CRM provider mappings for use in other modules
CRM_PROVIDER_MAP = {
    "hubspot": "crm_hubspot",
    "salesforce": "crm_salesforce",
    "gohighlevel": "crm_ghl"
}

# Export webhook manager for direct access
__all__ = [
    "add_buyer_webhook_support",
    "webhook_manager",
    "CRM_PROVIDER_MAP"
]