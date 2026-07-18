"""
Simplified Buyer Marketplace Webhooks for Empire OS.

Real-time webhook service for pushing enriched leads to buyer CRMs and dashboards.
Implements HubSpot, Salesforce, GoHighLevel integrations with retry logic.
Uses standard library where possible to avoid dependency issues.

Features:
- Exponential backoff retry with jitter
- HMAC payload verification
- Lead enrichment via Hub API
- Tenant-aware routing
- Dead-letter queue
- Health checks
- Minimal external dependencies
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware

# Global state
WEBHOOK_PORT = int(os.getenv("MARKETPLACE_WEBHOOK_PORT", "8090"))
HUB_URL = os.getenv("HUB_URL", "http://127.0.0.1:8081").rstrip("/")
CRM_CONFIG = os.getenv("CRM_CONFIG_PATH", "/root/empire_os/crm_config.json")
DEAD_LETTER_QUEUE = Path("/root/feedback/dead_letter_queue.jsonl")
DELIVERY_LOG = Path("/root/feedback/webhook_deliveries.jsonl")

# Retry configuration
MAX_RETRIES = int(os.getenv("CRM_RETRY_MAX", "5"))
INITIAL_RETRY_DELAY = int(os.getenv("CRM_RETRY_DELAY_SEC", "5"))
MAX_RETRY_DELAY = int(os.getenv("CRM_RETRY_MAX_DELAY_SEC", "300"))

# CRM providers
class CRMProvider(Enum):
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    GHL = "gohighlevel"

@dataclass
class CRMConfig:
    provider: CRMProvider
    api_url: str
    api_key: str
    webhook_secret: Optional[str] = None
    tenant_id: str
    enabled: bool = True
    retry_count: int = 0
    last_error: Optional[str] = None
    next_retry_after: Optional[datetime] = None

@dataclass
class LeadEnvelope:
    lead_id: str
    tenant_id: str
    buyer_id: str
    crm_config: CRMConfig
    raw_lead: Dict[str, Any]
    enriched_lead: Optional[Dict[str, Any]] = None
    enriched_at: Optional[datetime] = None
    delivery_attempts: List[Dict[str, Any]] = None
    status: str = "pending"
    created_at: datetime = None
    
    def __post_init__(self):
        if self.delivery_attempts is None:
            self.delivery_attempts = []
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)

@dataclass
class EnrichmentResult:
    success: bool
    enriched_lead: Dict[str, Any]
    enrichment_time_ms: int
    source: str

class WebhookManager:
    def __init__(self):
        self.crm_configs: Dict[str, CRMConfig] = {}
        self.dead_letter_queue: List[Dict[str, Any]] = []
        self.session_stats = {
            "total_leads": 0,
            "successful_deliveries": 0,
            "failed_deliveries": 0,
            "retry_counts": {},
            "provider_stats": {}
        }
        
    def load_crm_configs(self):
        """Load CRM configurations from file or environment."""
        try:
            if Path(CRM_CONFIG).exists():
                with open(CRM_CONFIG, 'r') as f:
                    configs = json.load(f)
                for config_data in configs:
                    config = CRMConfig(
                        provider=CRMProvider(config_data['provider']),
                        api_url=config_data['api_url'],
                        api_key=config_data['api_key'],
                        webhook_secret=config_data.get('webhook_secret'),
                        tenant_id=config_data['tenant_id'],
                        enabled=config_data.get('enabled', True),
                        retry_count=config_data.get('retry_count', 0),
                        last_error=config_data.get('last_error'),
                        next_retry_after=self._parse_datetime(
                            config_data['next_retry_after']
                        ) if config_data.get('next_retry_after') else None
                    )
                    self.crm_configs[config.tenant_id] = config
                    self.session_stats['provider_stats'][config.provider.value] = {
                        'enabled': 0,
                        'successful': 0,
                        'failed': 0
                    }
        except Exception as e:
            print(f"Failed to load CRM configs: {e}")
    
    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string from config."""
        try:
            return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        except Exception:
            return datetime.now(timezone.utc)
    
    def enrich_lead(self, lead: Dict[str, Any], config: CRMConfig) -> EnrichmentResult:
        """Enrich lead with additional data before CRM delivery."""
        start_time = time.time()
        
        try:
            enriched = lead.copy()
            
            # Basic enrichment
            enriched['enriched_at'] = datetime.now(timezone.utc).isoformat()
            enriched['crm_provider'] = config.provider.value
            enriched['tenant_id'] = config.tenant_id
            
            # Add basic lead scoring
            scoring = self._score_lead_for_buyer(lead, config)
            enriched['lead_score'] = scoring['score']
            enriched['qualification'] = scoring['qualification']
            
            # Add buyer-specific metadata via Hub API call
            payout = self._get_buyer_payout(config.tenant_id)
            enriched['buyer_payout'] = payout
            
            enrichment_time = int((time.time() - start_time) * 1000)
            
            return EnrichmentResult(
                success=True,
                enriched_lead=enriched,
                enrichment_time_ms=enrichment_time,
                source='multi_agent'
            )
            
        except Exception as e:
            print(f"Lead enrichment failed: {e}")
            return EnrichmentResult(
                success=False,
                enriched_lead=lead,
                enrichment_time_ms=int((time.time() - start_time) * 1000),
                source='error_fallback'
            )
    
    def _score_lead_for_buyer(self, lead: Dict[str, Any], config: CRMConfig) -> Dict[str, Any]:
        """Score lead based on buyer preferences and lead quality."""
        try:
            # Try to get scoring from Hub API
            score = self._get_lead_score(lead, config)
            if score >= 0:
                return score
        except Exception:
            pass
            
        # Default scoring
        score = 0
        if lead.get('email'):
            score += 30
        if lead.get('phone'):
            score += 20
        if lead.get('niche') and lead.get('metro'):
            score += 25
        if lead.get('website'):
            score += 25
            
        return {
            'score': min(score, 100),
            'qualification': 'qualified' if score >= 60 else 'prospect' if score >= 30 else 'cold'
        }
    
    def _get_lead_score(self, lead: Dict[str, Any], config: CRMConfig) -> Dict[str, Any]:
        """Get lead score from Hub API."""
        try:
            payload = {
                'lead': lead,
                'tenant_id': config.tenant_id,
                'provider': config.provider.value
            }
            
            data = json.dumps(payload).encode()
            
            req = urllib.request.Request(
                f"{HUB_URL}/v1/score-for-buyer",
                data=data,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
                    
        except Exception:
            pass
            
        return {'score': 0, 'qualification': 'unknown'}
    
    def _get_buyer_payout(self, tenant_id: str) -> Dict[str, Any]:
        """Get current buyer payout configuration."""
        try:
            req = urllib.request.Request(
                f"{HUB_URL}/v1/buyers/{tenant_id}/payout",
                method='GET'
            )
            
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    return json.loads(resp.read().decode())
        except Exception:
            pass
            
        return {
            'base_payout': 0,
            'tier': 'unknown',
            'fee_rate': 0
        }
    
    def _calculate_sync_priority(self, lead: Dict[str, Any]) -> int:
        """Calculate priority for CRM sync based on lead characteristics."""
        priority = 50  # base
        
        if lead.get('qualification') == 'qualified':
            priority += 30
        elif lead.get('qualification') == 'prospect':
            priority += 20
            
        if lead.get('lead_score', 0) >= 80:
            priority += 25
        elif lead.get('lead_score', 0) >= 60:
            priority += 15
            
        # Time-sensitive leads get higher priority
        if lead.get('time_sensitive'):
            priority += 20
            
        # Unavailable contact info decreases priority
        if not lead.get('email') or not lead.get('phone'):
            priority -= 20
            
        return min(priority, 100)
    
    def deliver_to_crm(self, envelope: LeadEnvelope) -> Tuple[bool, Dict[str, Any]]:
        """Deliver enriched lead to CRM with retry logic."""
        config = envelope.crm_config
        lead_to_deliver = envelope.enriched_lead or envelope.raw_lead
        
        # Check if we should retry
        if config.next_retry_after and datetime.now(timezone.utc) < config.next_retry_after:
            return False, {
                'status': 'throttled',
                'retry_after': config.next_retry_after.isoformat()
            }
        
        attempt = len(envelope.delivery_attempts) + 1
        retry_delay = self._calculate_retry_delay(attempt)
        
        try:
            success = False
            error_msg = None
            
            if config.provider == CRMProvider.HUBSPOT:
                success, error_msg = self._deliver_to_hubspot(lead_to_deliver, config)
            elif config.provider == CRMProvider.SALESFORCE:
                success, error_msg = self._deliver_to_salesforce(lead_to_deliver, config)
            elif config.provider == CRMProvider.GHL:
                success, error_msg = self._deliver_to_ghl(lead_to_deliver, config)
            
            # Record attempt
            attempt_record = {
                'attempt': attempt,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'success': success,
                'error': error_msg,
                'retry_delay': retry_delay if not success else 0
            }
            
            envelope.delivery_attempts.append(attempt_record)
            envelope.status = 'delivered' if success else 'failed'
            
            if success:
                # Update CRM config
                config.retry_count = 0
                config.last_error = None
                config.next_retry_after = None
                config.enabled = True
                
                # Update stats
                self.session_stats['successful_deliveries'] += 1
                self.session_stats['provider_stats'][config.provider.value]['successful'] += 1
                
                return True, {
                    'status': 'delivered',
                    'lead_id': envelope.lead_id,
                    'crm_tenant': config.tenant_id,
                    'attempt': attempt
                }
            else:
                # Update CRM config for next retry
                config.retry_count += 1
                config.last_error = error_msg
                config.next_retry_after = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
                config.enabled = config.retry_count < MAX_RETRIES
                
                # Update stats
                self.session_stats['failed_deliveries'] += 1
                self.session_stats['provider_stats'][config.provider.value]['failed'] += 1
                self.session_stats['retry_counts'][config.provider.value] = \
                    self.session_stats['retry_counts'].get(config.provider.value, 0) + 1
                
                # Log to dead letter queue if max retries exceeded
                if config.retry_count >= MAX_RETRIES:
                    dead_letter = {
                        'lead_id': envelope.lead_id,
                        'tenant_id': envelope.tenant_id,
                        'buyer_id': envelope.buyer_id,
                        'provider': config.provider.value,
                        'error': error_msg,
                        'last_attempt': attempt_record,
                        'next_retry': None,
                        'created_at': datetime.now(timezone.utc).isoformat()
                    }
                    self.dead_letter_queue.append(dead_letter)
                    self._log_to_file(dead_letter, DEAD_LETTER_QUEUE)
                
                return False, {
                    'status': 'failed',
                    'error': error_msg,
                    'attempt': attempt,
                    'retry_after': config.next_retry_after.isoformat() if config.next_retry_after else None,
                    'max_retries_reached': config.retry_count >= MAX_RETRIES
                }
                
        except Exception as e:
            # Unexpected error
            error_msg = str(e)
            config.retry_count += 1
            config.last_error = error_msg
            config.next_retry_after = datetime.now(timezone.utc) + timedelta(seconds=retry_delay)
            config.enabled = config.retry_count < MAX_RETRIES
            
            self.session_stats['failed_deliveries'] += 1
            
            return False, {
                'status': 'error',
                'error': error_msg,
                'attempt': attempt,
                'retry_after': config.next_retry_after.isoformat() if config.next_retry_after else None
            }
    
    def _calculate_retry_delay(self, attempt: int) -> int:
        """Calculate exponential backoff with jitter."""
        delay = min(INITIAL_RETRY_DELAY * (2 ** (attempt - 1)), MAX_RETRY_DELAY)
        
        # Add jitter to avoid thundering herd
        jitter = delay * 0.1 * (time.time() % 1)
        return int(delay + jitter)
    
    def _deliver_to_hubspot(self, lead: Dict[str, Any], config: CRMConfig) -> Tuple[bool, Optional[str]]:
        """Deliver lead to HubSpot CRM."""
        try:
            # Prepare HubSpot contact data
            hubspot_contact = {
                'properties': {
                    'email': lead.get('email', ''),
                    'phone': lead.get('phone', ''),
                    'firstname': lead.get('name', '').split()[0] if lead.get('name') else '',
                    'lastname': lead.get('name', '').split()[-1] if lead.get('name') and ' ' in lead.get('name') else '',
                    'company': lead.get('business_name', ''),
                    'website': lead.get('website', ''),
                    'lifecyclestage': lead.get('qualification', 'lead'),
                    'score': lead.get('lead_score', 0),
                    'niche': lead.get('niche', ''),
                    'metro': lead.get('metro', ''),
                    'lead_source': lead.get('source', 'marketplace'),
                    'buyer_tenant': config.tenant_id,
                    'enriched_at': lead.get('enriched_at'),
                    'qualification': lead.get('qualification'),
                    'buyer_payout': lead.get('buyer_payout', {}).get('base_payout', 0)
                }
            }
            
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'EmpireOS-BuyerMarketplace/1.0'
            }
            
            if config.webhook_secret:
                payload_str = json.dumps(hubspot_contact, sort_keys=True)
                signature = hmac.new(
                    config.webhook_secret.encode(),
                    payload_str.encode(),
                    hashlib.sha256
                ).hexdigest()
                headers['X-HubSpot-Signature'] = f'sha256={signature}'
            
            data = json.dumps(hubspot_contact).encode()
            req = urllib.request.Request(
                f"{config.api_url}/v1/contacts?hapid={config.tenant_id}",
                data=data,
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True, None
                else:
                    text = resp.read().decode()[:200]
                    return False, f"HubSpot HTTP {resp.status}: {text}"
                    
        except Exception as e:
            return False, str(e)
    
    def _deliver_to_salesforce(self, lead: Dict[str, Any], config: CRMConfig) -> Tuple[bool, Optional[str]]:
        """Deliver lead to Salesforce CRM."""
        try:
            salesforce_lead = {
                'Email': lead.get('email', ''),
                'Phone': lead.get('phone', ''),
                'FirstName': lead.get('name', '').split()[0] if lead.get('name') else '',
                'LastName': lead.get('name', '').split()[-1] if lead.get('name') and ' ' in lead.get('name') else '',
                'Company': lead.get('business_name', ''),
                'Website': lead.get('website', ''),
                'LeadSource': 'Marketplace',
                'Status': 'New' if lead.get('qualification') == 'qualified' else 'Open'
            }
            
            # Add custom fields if needed
            if lead.get('niche'):
                salesforce_lead['Niche__c'] = lead['niche']
            if lead.get('metro'):
                salesforce_lead['Metro__c'] = lead['metro']
            if lead.get('buyer_payout'):
                salesforce_lead['Buyer_Payout__c'] = lead['buyer_payout']['base_payout']
                
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'EmpireOS-BuyerMarketplace/1.0'
            }
            
            data = json.dumps(salesforce_lead).encode()
            req = urllib.request.Request(
                f"{config.api_url}/services/data/v56.0/sobjects/Lead",
                data=data,
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True, None
                else:
                    text = resp.read().decode()[:200]
                    return False, f"Salesforce HTTP {resp.status}: {text}"
                    
        except Exception as e:
            return False, str(e)
    
    def _deliver_to_ghl(self, lead: Dict[str, Any], config: CRMConfig) -> Tuple[bool, Optional[str]]:
        """Deliver lead to GoHighLevel CRM."""
        try:
            ghl_contact = {
                'firstName': lead.get('name', '').split()[0] if lead.get('name') else '',
                'lastName': lead.get('name', '').split()[-1] if lead.get('name') and ' ' in lead.get('name') else '',
                'email': lead.get('email', ''),
                'phone': lead.get('phone', ''),
                'company': lead.get('business_name', ''),
                'website': lead.get('website', ''),
                'customFields': {
                    'niche': lead.get('niche', ''),
                    'metro': lead.get('metro', ''),
                    'lead_score': lead.get('lead_score', 0),
                    'qualification': lead.get('qualification', ''),
                    'buyer_tenant': config.tenant_id,
                    'enriched_at': lead.get('enriched_at'),
                    'buyer_payout': lead.get('buyer_payout', {}).get('base_payout', 0)
                }
            }
            
            headers = {
                'Authorization': f'Bearer {config.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'EmpireOS-BuyerMarketplace/1.0'
            }
            
            data = json.dumps(ghl_contact).encode()
            req = urllib.request.Request(
                f"{config.api_url}/v1/contacts",
                data=data,
                headers=headers,
                method='POST'
            )
            
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True, None
                else:
                    text = resp.read().decode()[:200]
                    return False, f"GoHighLevel HTTP {resp.status}: {text}"
                    
        except Exception as e:
            return False, str(e)
    
    def _log_to_file(self, data: Dict[str, Any], path: Path):
        """Log data to file."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'a') as f:
                f.write(json.dumps(data, default=str) + "\n")
        except Exception as e:
            print(f"Failed to log to {path}: {e}")

# Initialize FastAPI app and webhook manager
app = FastAPI(
    title="Empire OS Buyer Marketplace Webhooks",
    description="Real-time lead delivery to buyer CRMs (HubSpot, Salesforce, GoHighLevel)",
    version="1.0.0"
)

webhook_manager = WebhookManager()

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load CRM configurations on startup
@app.on_event("startup")
async def startup_event():
    webhook_manager.load_crm_configs()
    print("Buyer Marketplace Webhook Manager started")
    print(f"Loaded {len(webhook_manager.crm_configs)} CRM configurations")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        'status': 'healthy',
        'crm_configs_count': len(webhook_manager.crm_configs),
        'total_leads_processed': webhook_manager.session_stats['total_leads'],
        'successful_deliveries': webhook_manager.session_stats['successful_deliveries'],
        'failed_deliveries': webhook_manager.session_stats['failed_deliveries'],
        'retry_counts': webhook_manager.session_stats['retry_counts'],
        'provider_stats': webhook_manager.session_stats['provider_stats'],
        'dead_letter_queue_size': len(webhook_manager.dead_letter_queue),
        'last_cleanup': datetime.now(timezone.utc).isoformat()
    }

@app.post("/v1/buyer-webhooks/lead")
async def receive_lead(request: Request):
    """
    Receive lead from marketplace and deliver to buyer CRMs.
    
    Expected payload:
    {
        "lead_id": "string",
        "tenant_id": "string",  // buy tenant
        "buyer_id": "string",
        "raw_lead": {...}
    }
    """
    try:
        payload = await request.json()
        
        # Validate required fields
        required_fields = ["lead_id", "tenant_id", "buyer_id", "raw_lead"]
        for field in required_fields:
            if field not in payload:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        tenant_id = payload["tenant_id"]
        
        # Get CRM configuration for tenant
        if tenant_id not in webhook_manager.crm_configs:
            raise HTTPException(status_code=404, detail=f"No CRM configuration for tenant: {tenant_id}")
        
        crm_config = webhook_manager.crm_configs[tenant_id]
        
        if not crm_config.enabled:
            raise HTTPException(status_code=423, detail="CRM delivery disabled for tenant")
        
        # Create envelope
        envelope = LeadEnvelope(
            lead_id=payload["lead_id"],
            tenant_id=tenant_id,
            buyer_id=payload["buyer_id"],
            crm_config=crm_config,
            raw_lead=payload["raw_lead"]
        )
        
        # Enrich lead
        enrichment = webhook_manager.enrich_lead(envelope.raw_lead, crm_config)
        envelope.enriched_lead = enrichment.enriched_lead
        envelope.enriched_at = datetime.now(timezone.utc)
        
        # Update stats
        webhook_manager.session_stats['total_leads'] += 1
        
        # Deliver to CRM (synchronously for now, can be async later)
        success, result = webhook_manager.deliver_to_crm(envelope)
        
        # Log delivery
        log_entry = {
            "lead_id": envelope.lead_id,
            "tenant_id": envelope.tenant_id,
            "provider": envelope.crm_config.provider.value,
            "success": success,
            "result": result,
            "enrichment_applied": envelope.enriched_lead is not None,
            "delivery_attempts": len(envelope.delivery_attempts),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        webhook_manager._log_to_file(log_entry, DELIVERY_LOG)
        
        # Cleanup dead letter queue periodically
        if len(webhook_manager.dead_letter_queue) > 1000:
            webhook_manager.cleanup_old_dead_letters(max_age_hours=24)
            
        return {
            "status": "accepted" if success else "processing_failed",
            "lead_id": envelope.lead_id,
            "tenant_id": envelope.tenant_id,
            "enrichment_time_ms": enrichment.enrichment_time_ms,
            "enqueue_time": datetime.now(timezone.utc).isoformat(),
            "crm_status": result
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Failed to process lead: {error_msg}")
        return {"status": "error", "error": error_msg}

@app.get("/v1/buyer-webhooks/dead-letter")
async def get_dead_letter_queue(limit: int = 100):
    """Get recent dead letter queue entries."""
    return {
        "dead_letters": webhook_manager.dead_letter_queue[:limit],
        "total_count": len(webhook_manager.dead_letter_queue)
    }

@app.delete("/v1/buyer-webhooks/dead-letter/{lead_id}")
async def remove_from_dead_letter(lead_id: str):
    """Remove specific dead letter entry."""
    webhook_manager.dead_letter_queue = [
        item for item in webhook_manager.dead_letter_queue if item['lead_id'] != lead_id
    ]
    return {"status": "removed", "lead_id": lead_id}

@app.get("/v1/buyer-webhooks/stats")
async def get_stats():
    """Get webhook delivery statistics."""
    return {
        'status': 'healthy',
        'crm_configs_count': len(webhook_manager.crm_configs),
        'total_leads_processed': webhook_manager.session_stats['total_leads'],
        'successful_deliveries': webhook_manager.session_stats['successful_deliveries'],
        'failed_deliveries': webhook_manager.session_stats['failed_deliveries'],
        'retry_counts': webhook_manager.session_stats['retry_counts'],
        'provider_stats': webhook_manager.session_stats['provider_stats'],
        'dead_letter_queue_size': len(webhook_manager.dead_letter_queue),
        'last_cleanup': datetime.now(timezone.utc).isoformat()
    }

@app.post("/v1/buyer-webhooks/cleanup")
async def cleanup():
    """Trigger cleanup of old dead letter entries."""
    webhook_manager.cleanup_old_dead_letters(max_age_hours=24)
    return {"status": "cleanup_completed"}

def webhook_manager_cleanup_old_dead_letters(webhook_manager, max_age_hours: int = 24):
    """Clean up old dead letter entries."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    
    webhook_manager.dead_letter_queue = [
        item for item in webhook_manager.dead_letter_queue
        if datetime.fromisoformat(item['created_at']) > cutoff
    ]

# CRM-specific webhook endpoints for bidirectional sync
@app.post("/webhooks/hubspot")
async def hubspot_webhook(request: Request):
    """HubSpot webhook for changes to contacts (bidirectional sync)."""
    try:
        data = await request.json()
        
        payload = {
            "source": "hubspot",
            "event": data.get('event_type'),
            "contact": data.get('contact'),
            "properties": data.get('properties'),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Forward to hub for processing
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{HUB_URL}/v1/crm/hubspot-webhook",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass  # Best effort
            
    except Exception as e:
        print(f"HubSpot webhook error: {e}")
        
    return {"status": "processed"}

@app.post("/webhooks/salesforce")
async def salesforce_webhook(request: Request):
    """Salesforce webhook for lead/contact changes."""
    try:
        data = await request.json()
        
        payload = {
            "source": "salesforce",
            "event_type": data.get("eventType", "unknown"),
            "sfdc_data": data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{HUB_URL}/v1/crm/salesforce-webhook",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass  # Best effort
            
    except Exception as e:
        print(f"Salesforce webhook error: {e}")
        
    return {"status": "processed"}

@app.post("/webhooks/gohighlevel")
async def ghl_webhook(request: Request):
    """GoHighLevel webhook for contact updates."""
    try:
        data = await request.json()
        
        payload = {
            "source": "gohighlevel",
            "event": data.get("type", "unknown"),
            "contact": data.get("contact"),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{HUB_URL}/v1/crm/ghl-webhook",
            data=data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass  # Best effort
            
    except Exception as e:
        print(f"GoHighLevel webhook error: {e}")
        
    return {"status": "processed"}

@app.get("/")
async def root():
    """API information."""
    return {
        "service": "Empire OS Buyer Marketplace Webhooks",
        "version": "1.0.0",
        "description": "Real-time lead delivery to buyer CRMs",
        "endpoints": [
            "/health - Health check",
            "/v1/buyer-webhooks/lead - Receive leads",
            "/v1/buyer-webhooks/dead-letter - View dead letter queue",
            "/v1/buyer-webhooks/stats - Delivery statistics",
            "/v1/buyer-webhooks/cleanup - Cleanup old entries",
            "/webhooks/hubspot - HubSpot webhook",
            "/webhooks/salesforce - Salesforce webhook",
            "/webhooks/gohighlevel - GoHighLevel webhook"
        ]
    }

if __name__ == "__main__":
    print("Starting Buyer Marketplace Webhook Manager...")
    print(f"Port: {WEBHOOK_PORT}")
    print(f"Hub URL: {HUB_URL}")
    print(f"CRM Config: {CRM_CONFIG}")
    
    # Note: In production, use a proper ASGI server
    # This is for demonstration only
    import uvicorn
    uvicorn.run(
        "empire_os.buyer_marketplace_webhooks:app",
        host="0.0.0.0",
        port=WEBHOOK_PORT,
        access_log=True,
        log_level="info"
    )