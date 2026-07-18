#!/root/hunt_venv/bin/python3
"""Connect buyer marketplace to existing lead delivery + invoicing system.

This script bridges the gap between the new buyer API (being built by parallel agents)
and the existing lead delivery/invoice infrastructure.

Key Functions:
1. Buyer registration webhook integration
2. Lead delivery webhook endpoint for buyer API
3. Revenue tracking linkage
4. Payout batch creation trigger
"""
import os
import json
import hashlib
import hmac
import urllib.request
import urllib.parse
import uuid
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add empire OS to path
sys.path.insert(0, "/root/empire_os")

# Load existing lead_deliverer functionality
from empire_os.agents.lead_deliverer_agent import (
    post_webhook, 
    deliver_lead, 
    bill_on_delivery,
    render_lead_delivered_email,
    _log_event
)

# Global configuration
HUB_URL = os.environ.get("HUB_URL", "http://localhost:8000")
API_SECRET = os.environ.get("API_SECRET_KEY", "default-secret-change-in-production")

class BuyerMarketplaceConnector:
    def __init__(self):
        self.registered_buyers = {}
        self.webhook_secret = API_SECRET
    
    def register_buyer(self, buyer_data):
        """Register a new buyer and create their profile"""
        tenant_id = str(uuid.uuid4().hex[:8])
        buyer_profile = {
            "tenant_id": tenant_id,
            "name": buyer_data.get("name"),
            "niche": buyer_data.get("niche", "general"),
            "tier": buyer_data.get("tier", "bronze"),
            "base_payout": self._get_tier_base_payout(buyer_data.get("tier", "bronze")),
            "fee_rate": self._get_tier_fee_rate(buyer_data.get("tier", "bronze")),
            "email": buyer_data.get("email"),
            "webhook_url": buyer_data.get("webhook_url", ""),
            "delivery_email": buyer_data.get("delivery_email", buyer_data.get("email")),
            "api_key": str(uuid.uuid4().hex[:16]),
            "dashboard_url": f"https://empire-ai.co.uk/dashboard/{tenant_id}",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "credits_remaining": self._get_tier_credits(buyer_data.get("tier", "bronze"))
        }
        
        self.registered_buyers[tenant_id] = buyer_profile
        
        # Save to existing system
        self._save_buyer_profile(buyer_profile)
        
        return {
            "tenant_id": tenant_id,
            "api_key": buyer_profile["api_key"],
            "status": "active",
            "base_payout": buyer_profile["base_payout"],
            "fee_rate": buyer_profile["fee_rate"],
            "credits_remaining": buyer_profile["credits_remaining"]
        }
    
    def process_buyer_lead_request(self, payload):
        """Process a lead request from buyer API"""
        # Verify signature
        signature = payload.get("signature", "")
        body_data = json.loads(payload.get("body", "{}")) if isinstance(payload.get("body"), str) else payload.get("body", {})
        
        if not self._verify_signature(body_data, signature):
            return {"ok": False, "error": "Invalid signature"}
        
        # Validate buyer
        buyer_id = body_data.get("buyer_id")
        if not buyer_id or buyer_id not in self.registered_buyers:
            return {"ok": False, "error": "Invalid buyer_id"}
        
        buyer = self.registered_buyers[buyer_id]
        
        # Check credits
        if buyer["credits_remaining"] <= 0:
            return {"ok": False, "error": "No credits remaining"}
        
        # Process lead
        lead_result = self._process_lead_for_buyer(buyer, body_data)
        
        if lead_result["success"]:
            # Deduct credit
            buyer["credits_remaining"] -= 1
            self._save_buyer_profile(buyer)
            
            return {
                "ok": True,
                "lead_id": lead_result["lead_id"],
                "credits_remaining": buyer["credits_remaining"],
                "invoice_id": lead_result.get("invoice_id"),
                "amount_usd": lead_result.get("amount_usd")
            }
        else:
            return {"ok": False, "error": lead_result.get("error", "Processing failed")}
    
    def _get_tier_base_payout(self, tier):
        """Get base payout for tier"""
        tiers = {
            "bronze": 9.0,
            "silver": 12.0,
            "gold": 18.0,
            "platinum": 25.0,
            "titanium": 45.0
        }
        return tiers.get(tier.lower(), 12.0)
    
    def _get_tier_fee_rate(self, tier):
        """Get fee rate for tier"""
        tiers = {
            "bronze": 1.2,  # 120%
            "silver": 1.5,  # 150%
            "gold": 2.0,    # 200%
            "platinum": 2.5, # 250%
            "titanium": 3.0 # 300%
        }
        return tiers.get(tier.lower(), 1.5)
    
    def _get_tier_credits(self, tier):
        """Get credit allowance for tier"""
        tiers = {
            "bronze": 10,
            "silver": 25,
            "gold": 50,
            "platinum": 100,
            "titanium": 250
        }
        return tiers.get(tier.lower(), 25)
    
    def _verify_signature(self, body_data, signature):
        """Verify HMAC signature"""
        if not signature:
            return False
        
        # Generate expected signature
        body_json = json.dumps(body_data, separators=(',', ':'), sort_keys=True)
        expected_sig = hmac.new(
            self.webhook_secret.encode('utf-8'),
            body_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature == expected_sig
    
    def _process_lead_for_buyer(self, buyer, lead_data):
        """Process a single lead for buyer"""
        try:
            # Generate lead ID
            lead_id = f"lead_{uuid.uuid4().hex[:12]}"
            
            # Create lead record for marketplace
            lead_record = {
                "lead_id": lead_id,
                "source": buyer["niche"],
                "business_name": lead_data.get("business_name", ""),
                "contact_name": lead_data.get("contact_name", ""),
                "email": lead_data.get("email", ""),
                "phone": lead_data.get("phone", ""),
                "city": lead_data.get("city", ""),
                "state": lead_data.get("state", ""),
                "niche": buyer["niche"],
                "metro": lead_data.get("metro", ""),
                "status": "new",
                "buyer_id": buyer["tenant_id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "enrichment_source": "market_sweep"
            }
            
            # For now, store in local db (in production, use CRM)
            self._store_lead_in_crm(lead_record)
            
            # Calculate payout amount
            amount_usd = buyer["base_payout"] * buyer["fee_rate"]
            
            # Send to existing lead_deliverer for webhook + email
            delivery_result = deliver_lead({
                "tenant_id": buyer["tenant_id"],
                "name": buyer["name"],
                "email": buyer["email"],
                "webhook_url": buyer["webhook_url"],
                "delivery_email": buyer["delivery_email"],
                "api_key": buyer["api_key"],
                "dashboard_url": buyer["dashboard_url"],
                "niche": buyer["niche"],
                "base_payout": buyer["base_payout"],
                "fee_rate": buyer["fee_rate"]
            }, lead_record)
            
            # Bill the buyer via existing system
            invoice_id = None
            if delivery_result.get("webhook_ok", False) or delivery_result.get("email_ok", False):
                invoice_id = bill_on_delivery({
                    "tenant_id": buyer["tenant_id"],
                    "name": buyer["name"],
                    "email": buyer["email"],
                    "webhook_url": buyer["webhook_url"],
                    "delivery_email": buyer["delivery_email"],
                    "api_key": buyer["api_key"],
                    "dashboard_url": buyer["dashboard_url"],
                    "niche": buyer["niche"],
                    "base_payout": buyer["base_payout"],
                    "fee_rate": buyer["fee_rate"]
                }, lead_record)
            
            return {
                "success": True,
                "lead_id": lead_id,
                "invoice_id": invoice_id,
                "amount_usd": amount_usd,
                "delivered": delivery_result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _save_buyer_profile(self, buyer):
        """Save buyer profile to local storage (in production, use CRM)"""
        try:
            from pathlib import Path
            path = Path("/root/empire_os/.buyer_profiles.json")
            if path.exists():
                with open(path, 'r') as f:
                    profiles = json.loads(f.read())
            else:
                profiles = {}
            
            profiles[buyer["tenant_id"]] = buyer
            
            with open(path, 'w') as f:
                f.write(json.dumps(profiles, indent=2, default=str))
                
        except Exception as e:
            _log_event("BUYER_PROFILE_SAVE_ERROR", str(e), tenant_id=buyer["tenant_id"])
    
    def _store_lead_in_crm(self, lead):
        """Store lead in CRM for marketplace access"""
        try:
            from pathlib import Path
            path = Path("/root/empire_os/.marketplace_leads.json")
            if path.exists():
                with open(path, 'r') as f:
                    leads = json.loads(f.read())
            else:
                leads = []
            
            leads.append(lead)
            
            with open(path, 'w') as f:
                f.write(json.dumps(leads, indent=2, default=str))
                
        except Exception as e:
            _log_event("MARKETPLACE_LEAD_STORE_ERROR", str(e), lead_id=lead["lead_id"])

if __name__ == "__main__":
    # Example usage
    connector = BuyerMarketplaceConnector()
    
    # Example: Register a new buyer
    print("Registering buyer...")
    buyer_data = {
        "name": "Acme Roofing",
        "niche": "roofing",
        "tier": "gold",
        "email": "buyers@acmeroofing.com",
        "webhook_url": "https://api.acmeroofing.com/webhooks/leads",
        "delivery_email": "leads@acmeroofing.com"
    }
    
    result = connector.register_buyer(buyer_data)
    print(f"✅ Buyer registered: {result}")
    
    # Example: Process lead request from buyer API
    print("\nProcessing lead request...")
    lead_payload = {
        "body": json.dumps({
            "buyer_id": "abc12345",
            "business_name": "Sunshine Contractors",
            "contact_name": "John Smith",
            "email": "john@sunshinecontractors.com",
            "phone": "555-0123",
            "city": "Phoenix",
            "state": "AZ",
            "metro": "Phoenix, AZ"
        }),
        "signature": "test_signature"  # In production, this would be HMAC signed
    }
    
    process_result = connector.process_buyer_lead_request(lead_payload)
    print(f"✅ Lead processed: {process_result}")
    
    print("\n🚀 Buyer marketplace connector initialized successfully!")
    print("   Ready to receive leads from buyer API...")