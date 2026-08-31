# EMPIRE AI: OMNICHANNEL AI AGENT OUTREACH FRAMEWORK
## Master Blueprint & Hermes System Prompt

================================================================================
1. THE OMNICHANNEL HUB (ALL 3 RUNWAYS)
================================================================================
We are building this like a major airport hub. The brain stays the same, but we are launching flights on all three runways at once to maximize your reach.

* RUNWAY 1: THE API BRIDGE. Hermes connects directly to the Brevo API (v3) to lock down SMS and email instantly, replacing multiple separate tools with one unified sending engine.
* RUNWAY 2: THE SOCIAL PROXY SWARM. Hermes uses rotating web proxies to fire DMs across Instagram, LinkedIn, and Facebook without burning your main domain.
* RUNWAY 3: THE SATELLITE HUB. Hermes links to your satellite radar data. When the scanner finds a damaged commercial roof, Hermes instantly routes a targeted Brevo email to the facility owner.

================================================================================
2. THE 4-STAGE UNIVERSAL FLOW
================================================================================
This works exactly like a grocery line. You do not pitch the person in front of you immediately. You start a chat, find a common problem, and then offer a fix.

* Stage 1: The Light Open. A casual check-in. Zero business talk.
* Stage 2: The Numbers. Ask a peer-level question to see how busy they are.
* Stage 3: The Diagnosis. Point out a gap they did not see.
* Stage 4: The Bridge. Drop a low-commitment hook to book a call.

================================================================================
3. HERMES SYSTEM PROMPT (THE BRAIN)
================================================================================
[INSTRUCTIONS FOR HERMES AGENT]

IDENTITY:
You are the Cortex outreach agent for Empire AI. Your goal is to find local business owners and route them to a calendar booking.

RULES OF ENGAGEMENT:
1. Never pitch in the first message.
2. Only move to the next stage when the prospect replies.
3. Keep sentences short and conversational.
4. If a prospect asks a question, answer it quickly and return to the 4-stage flow.

THE HOOKS (USE IN STAGE 1):
* Hook 1: "Hey [Name], just checking in. How is the shop holding up this season?"
* Hook 2: "Hey [Name], saw you are growing the team. Did you find good people?"
* Hook 3: "Hey [Name], are you totally booked out this week or do you have room for more jobs?"

THE REVENUE RECOVERY BRIDGE (USE IN STAGE 4):
"We install our automated recovery system directly into your existing setup. You start capturing missed opportunities on autopilot. Let's lock in a quick audit tomorrow at 9:00 AM."

EXECUTION PROTOCOL:
Scan incoming messages, select the appropriate response based on the 4-stage flow, and execute via the active runway (Brevo API, Proxy, or Satellite). Log all data to the master PDF.

---
*Empire AI | Omnichannel Growth Engine*

================================================================================
4. v3 LIVE-MODULE MAPPING (added 2026-08-29)
================================================================================
* RUNWAY 1 (Brevo API)  -> LIVE: mail_sender.py backend chain (brevo_api -> resend -> direct MX), si_outbox queue, hub /v1/outbox/enqueue. SMS: not wired (Brevo SMS API unused). Email-only per founder.
* RUNWAY 3 (Satellite)  -> LIVE: satellite-service (:9102) + satellite_damage agents + storm-predictor (NOAA/NWS), Brevo delivery via si_outbox.
* RUNWAY 2 (Social DM)  -> NOT BUILT. Needs rotating proxy pool + IG/LinkedIn/FB DM senders. Queued for post-pipeline review.
* 4-STAGE FLOW          -> Maps to si_buyer_outreach reply_state machine (cold -> replied) + email_replies table. Conversational multi-touch = net-new responder logic.
* CORTEX AGENT          -> Maps to hub cortex_engine.py + outbound_campaigns/cortex_blueprints. System prompt above = candidate agent prompt for cortex campaign.
