# EmpireOS — Call-loss intelligence and buyer-side review
27 October 2026 | Original competitor/call acquisition research | OBSERVE

## Live accessible evidence
Original commercial pulse: runtime/revenue/lead_smart/commercial_pulse/latest.json.
Observed 27 October 11:36:56 UTC; supervised-pilot campaign expiry recorded as 26 October 21:44 UTC. This timestamp is NOT proof of current Ringba campaign configuration. The pulse has zero matching call rows in its bounded returned Ringba window, NOT proof of zero calls outside that window. Human buyer connection, payable acceptance and actual cash settlement remain unverified. Site-handoff count in pulse is 0, which does not mean zero site sessions. Original effective pilot is PREACTIVATION; traffic and routing OFF. Root-owned call-to-cash source NOT opened.

## Direct original Ringba documentation
- https://support.ringba.com/hc/en-us/articles/26894023126551 — Call Details Report: Connected, Connected Call Length, Hangup, Block Reason, Incomplete Call Reason, No Conversion Reason, No Payout Reason, Approved Adjustment and amounts.
- https://support.ringba.com/hc/en-us/articles/24286807682839-Ringba-Dashboard — Incoming, Connected, No Connect, No Targets, No Answer, Error.
Ringba target-connected can mean IVR, hold music or queue; NOT proof a human answered. Dashboard No Answer may represent target attempts, not distinct inbound calls. Do not add raw target attempts to per-unique-call reason buckets. Provider payout is NOT a settled bank receipt.

## Loss classification contract — one terminal outcome per distinct incoming call
NO_ELIGIBLE_TARGET; TARGET_NO_ANSWER; TARGET_BUSY; TARGET_ERROR; CALLER_LEFT_BEFORE_CONNECTION; BLOCKED_BY_SOURCE_POLICY; UNCLASSIFIED_NO_CONNECT. The sum must match exact (incoming minus target-connected) in the independently verified original commercial owner's same-source cohort.

Human-answered but nonpayable classifications: WRONG_SERVICE; WRONG_GEOGRAPHY; BELOW_CONTRACT_DURATION; DUPLICATE_OR_REPEAT; BUYER_DECLINED_UNDER_WRITTEN_TERMS; DISPUTED_OR_REVERSAL_PENDING; UNCLASSIFIED_NOT_PAYABLE. Sum must match (human answered minus accepted payable), requiring the commercial owner's own definitions and explicit source-authorised truth. A buyer no-answer event is not publisher wrongdoing and commercial disputes are not proof of fraud.

## What now exists
Original competitor intelligence can read new evidence snapshot at runtime/competitive_intelligence/call_loss_readiness_latest.json. Its independent pure evaluator can review future **original-owner-approved, unique-call deduplicated aggregate** cohorts, fail closed if stage counts or reason totals contradict each other and keep unknown counts as null. No raw call IDs, ANI, individual recordings, payment credentials, call-route edits or traffic activations.

## Original system owner handoff
1. Commercial owner: verify actual Ringba campaign expiry against the observed 26 Oct timestamp and validate buyer operating hours/source rights without activation from research.
2. Ringba owner: produce authorised, bounded aggregate unique inbound calls, target-connected, separately human-answered where verifiable, reason-coded terminal non-connects, payout and dispute records. No PII. Explicitly label raw target-attempt counters to avoid mixing units.
3. Buyer acceptance owner: verify buyer written payable rules, matching geography/service, eligible source, duplicate duration and disposition; no invented sale from payout columns.
4. CRO/website owner: join consent-compliant, real first-party channel visit -> ZIP interaction -> voluntarily initiated call to Ringba provider outcomes. Do not change website without current website owner.
5. Finance/CRU owner: separately verify real cash settlements, reversals, source costs and margin; no inferred ROAS from vendor marketing case studies.

**Policy:** No new agent, timer, PostgreSQL database, outbound, route mutation, paid spend, automatic experiment, SEO change or revenue recognition.
