#!/usr/bin/env python3
"""
Senior List Building and Email Marketing Agent
Combines lead discovery, list segmentation, email drafting, and nurture sequences.
Incorporates SOUL copywriting guidelines and markdown guard rails.
Integrates with Gauntlet Loop for performance feedback.
Uses USDT BSC for payments (updated from BSC).
"""
import json, os, sys, time, sqlite3, hashlib, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
from empire_os.agent_core import OllamaClient
from empire_os.synthetic_agents import SyntheticAgent
from empire_os.whitelabel import get_brand
from empire_os.agents.render_founder_email import render_email

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8080")
TICK_INTERVAL = 900  # 15 min
DB = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = "/root/empire_os/feedback"
GAUNTLET_ENDPOINT = f"{HUB}/v1/gauntlet/feedback"  # Assume endpoint exists

# SOUL Guidelines: Direct, Specific, Operator-grade, No fluff, No exclamation points
SOUL_RULES = {
    "no_exclamation": r"!",
    "no_fluff_phrases": [
        r"welcome to our comprehensive",
        r"we leverage cutting-edge",
        r"your perfect partner awaits",
        r"hope you're well",
        r"reaching out",
        r"touching base",
        r"just checking in",
        r"I noticed",
        r"I saw",
    ],
    "must_have_specifics": [
        r"\d+",  # at least one number
        r"[A-Z][a-z]+ \d+",  # e.g., Dallas HVAC
    ],
}

# Markdown guard rails for email content
MARKDOWN_RULES = {
    "no_raw_html": r"<[^>]+>",  # basic HTML tag detection
    "max_line_length": 100,
    "required_placeholders": ["{business_name}", "{city}", "{niche}"],
}

class SeniorListEmailAgent(SyntheticAgent):
    """Senior agent for list building and email marketing."""

    def observe(self) -> dict:
        """Gather leads, enrichment status, and current campaigns."""
        state = {
            "leads_needing_enrichment": [],
            "leads_ready_for_email": [],
            "campaign_performance": {},
            "errors": [],
        }

        try:
            # Get leads that need enrichment (missing email or low quality)
            r = urllib.request.urlopen(HUB + "/v1/leads?needs_enrichment=true&limit=50", timeout=10)
            leads = json.loads(r.read()).get("leads", [])
            state["leads_needing_enrichment"] = leads
        except Exception as e:
            state["errors"].append(f"fetch leads: {e}")

        try:
            # Get leads that are enriched and ready for email sequences
            r = urllib.request.urlopen(HUB + "/v1/leads?sequence_step<3&limit=50", timeout=10)
            leads = json.loads(r.read()).get("leads", [])
            state["leads_ready_for_email"] = leads
        except Exception as e:
            state["errors"].append(f"fetch ready leads: {e}")

        try:
            # Get recent campaign performance from Gauntlet Loop
            r = urllib.request.urlopen(HUB + "/v1/gauntlet/recent?limit=10", timeout=10)
            state["campaign_performance"] = json.loads(r.read()).get("metrics", {})
        except Exception:
            pass  # Gauntlet Loop may not be available yet

        return state

    def reason(self, state: dict) -> str:
        """Decide what list building and email actions to take."""
        if state.get("errors"):
            return json.dumps({"action": "handle_errors", "errors": state["errors"]})

        leads_to_enrich = state.get("leads_needing_enrichment", [])
        leads_to_email = state.get("leads_ready_for_email", [])

        # Prioritize enrichment if we have many leads needing it
        if len(leads_to_enrich) > 20:
            return json.dumps({
                "action": "enrich_leads",
                "leads": leads_to_enrich[:30],  # batch of 30
                "reason": "High volume of leads needing enrichment"
            })

        if leads_to_email:
            # Determine email type based on sequence step or campaign performance
            email_type = self._determine_email_type(leads_to_email[0], state["campaign_performance"])
            return json.dumps({
                "action": "send_email_sequence",
                "leads": leads_to_email[:20],  # batch of 20
                "email_type": email_type,
                "reason": f"Sending {email_type} emails to nurture leads"
            })

        # Default: do light enrichment
        return json.dumps({
            "action": "enrich_leads",
            "leads": leads_to_enrich[:10] if leads_to_enrich else [],
            "reason": "Maintenance enrichment"
        })

    def act(self, decision: str) -> dict:
        """Execute the decided action."""
        try:
            d = json.loads(decision)
            action = d.get("action")

            if action == "enrich_leads":
                return self._enrich_leads(d.get("leads", []))
            elif action == "send_email_sequence":
                return self._send_email_sequence(d.get("leads", []), d.get("email_type", "value"))
            elif action == "handle_errors":
                return self._handle_errors(d.get("errors", []))
            else:
                return {"summary": f"unknown action: {action}"}
        except Exception as e:
            return {"summary": "agent-error", "error": str(e)}

    def _enrich_leads(self, leads):
        """Enrich lead data using waterfall (website, pattern, Hunter)."""
        enriched = 0
        for lead in leads:
            # Use enrichment.py waterfall
            # For simplicity, we'll call the hub enrichment endpoint
            try:
                payload = json.dumps({
                    "prospect_id": lead.get("prospect_id"),
                    "website": lead.get("url"),
                    "business_name": lead.get("business_name"),
                }).encode()
                req = urllib.request.Request(
                    f"{HUB}/v1/enrich",
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=15) as r:
                    res = json.loads(r.read())
                if res.get("enriched"):
                    enriched += 1
            except Exception:
                pass  # Continue on individual failures
        return {"summary": f"enriched-{enriched}-leads", "count": enriched}

    def _send_email_sequence(self, leads, email_type):
        """Send emails following SOUL guidelines and using branded templates."""
        sent = 0
        for lead in leads:
            try:
                # Extract lead data
                pid = lead.get("prospect_id")
                name = lead.get("business_name", "there")
                email = lead.get("email")
                niche = lead.get("niche", "b2b")
                metro = lead.get("metro", "your area")
                seq_step = lead.get("sequence_step", 0)

                if not email or "@example" in email:
                    continue

                # Generate email content based on type and SOUL rules
                subject, body = self._generate_email_content(
                    name, niche, metro, email_type, seq_step
                )

                # Apply SOUL guard rails
                if not self._passes_soul_rules(subject, body):
                    continue  # Skip if violates SOUL

                # Apply markdown guard rails
                if not self._passes_markdown_rules(body):
                    continue  # Skip if violates markdown rules

                # Queue email via hub (uses Brevo/Resend via /v1/outbox/enqueue)
                self._queue_email_via_hub(email, subject, body, lead)

                # Update lead sequence step
                self._update_lead_sequence(pid, seq_step + 1)

                sent += 1

                # Report to Gauntlet Loop (fire and forget)
                self._report_to_gauntlet(lead, email_type, "sent")

            except Exception as e:
                # Log individual lead failure but continue
                self._log_error(f"lead {lead.get('prospect_id')}: {e}")
                continue

        return {"summary": f"queued-{sent}-emails", "count": sent}

    def _generate_email_content(self, name, niche, metro, email_type, seq_step):
        """Generate subject and body based on email type and SOUL."""
        # Use the branded renderer for founder emails, but adapt for sequence
        if email_type == "founder":
            html, text, subject = render_email(
                business_name=name,
                city=metro,
                state="",
                niche=niche,
                metro=metro,
            )
            return subject, text  # Use text version for SOUL compliance check
        else:
            # For nurture sequences, use templates from nurture_daemon
            # But we'll generate simple SOUL-compliant text
            templates = {
                "value": f"Roof damage spikes in {metro} every storm season. We track the addresses. We grade the leads. You get the hot ones. No cost to look.",
                "nudge": f"Last storm cycle we saw 400+ roof leads in {metro}. Most went cold because nobody called fast enough. Want the list?",
                "ask": f"5-minute call. I'll show you the feed. You pay per seated lead in USDT. Reply 'yes' and I'll send the link."
            }
            body = templates.get(email_type, templates["value"])
            subject = f"Empire OS — {email_type.title()} ({metro or 'leads'})"
            return subject, body

    def _passes_soul_rules(self, subject, body):
        """Check if content follows SOUL copywriting guidelines."""
        combined = f"{subject} {body}"

        # No exclamation points
        if re.search(SOUL_RULES["no_exclamation"], combined):
            return False

        # No fluff phrases
        for pattern in SOUL_RULES["no_fluff_phrases"]:
            if re.search(pattern, combined, re.IGNORECASE):
                return False

        # Must have at least one number (specificity)
        if not re.search(SOUL_RULES["must_have_specifics"][0], combined):
            return False

        # Optional: check for specific location/niche pattern
        # Not strictly required but good to have

        return True

    def _passes_markdown_rules(self, body):
        """Basic markdown guard rails for email content."""
        # No raw HTML tags (we want plain text for SOUL)
        if re.search(MARKDOWN_RULES["no_raw_html"], body):
            return False

        # Line length check
        lines = body.split("\n")
        for line in lines:
            if len(line) > MARKDOWN_RULES["max_line_length"]:
                return False

        # Check for required placeholders (if applicable)
        # For nurture emails, placeholders may not be needed
        # For founder emails, they are handled in render_email
        return True

    def _queue_email_via_hub(self, to_email, subject, body, lead_data):
        """Queue email via hub's /v1/outbox/enqueue endpoint (uses Brevo)."""
        try:
            payload = json.dumps({
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "source": "senior_list_email",
                "metadata": json.dumps({
                    "lead_id": lead_data.get("prospect_id"),
                    "niche": lead_data.get("niche"),
                    "metro": lead_data.get("metro"),
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            }).encode()
            req = urllib.request.Request(
                f"{HUB}/v1/outbox/enqueue",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                res = json.loads(r.read())
            return res.get("queued", False)
        except Exception as e:
            self._log_error(f"queue email failed: {e}")
            return False

    def _update_lead_sequence(self, prospect_id, new_step):
        """Update lead's sequence step in database."""
        try:
            payload = json.dumps({
                "prospect_id": prospect_id,
                "sequence_step": new_step
            }).encode()
            req = urllib.request.Request(
                f"{HUB}/v1/leads/{prospect_id}/sequence",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="PUT"
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                pass
        except Exception:
            pass  # Non-critical

    def _report_to_gauntlet(self, lead_data, email_type, status):
        """Report email sent to Gauntlet Loop for performance tracking."""
        try:
            payload = json.dumps({
                "prospect_id": lead_data.get("prospect_id"),
                "email_type": email_type,
                "status": status,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "niche": lead_data.get("niche"),
                "metro": lead_data.get("metro")
            }).encode()
            req = urllib.request.Request(
                GAUNTLET_ENDPOINT,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                pass
        except Exception:
            pass  # Gauntlet Loop may not be ready; non-critical

    def _handle_errors(self, errors):
        """Handle observed errors."""
        # Log errors and optionally alert
        for err in errors:
            self._log_error(err)
        return {"summary": "errors-logged", "count": len(errors)}

    def _log_error(self, msg):
        """Log error to feedback directory."""
        try:
            Path(FEEDBACK_DIR).mkdir(parents=True, exist_ok=True)
            with open(Path(FEEDBACK_DIR) / "senior_agent_errors.jsonl", "a") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "error": msg
                }) + "\n")
        except Exception:
            pass

if __name__ == "__main__":
    import os
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
    agent = SeniorListEmailAgent(
        name="senior-list-email-agent",
        role="senior_list_email",
        health_url="http://localhost:9102/health",
    )
    print(f"Senior list/email agent starting — tick interval {TICK_INTERVAL}s")
    consecutive_failures = 0
    while True:
        try:
            result = agent.tick()
            consecutive_failures = 0
            print(json.dumps({
                "cycle": result.get("cycle"),
                "summary": result.get("result", {}).get("summary", "")
            }))
        except Exception as e:
            consecutive_failures += 1
            backoff = min(60 * consecutive_failures, 600)
            print(json.dumps({
                "error": str(e),
                "backoff": backoff,
                "failures": consecutive_failures
            }))
            time.sleep(backoff)
            continue
        time.sleep(TICK_INTERVAL)