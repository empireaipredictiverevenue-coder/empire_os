# Empire Deliverability Moat

Current outbound tools commonly offer:
- warm-up pools
- mailbox rotation
- DNS/authentication checks
- inbox-placement tests
- blocklist monitoring
- bounce-rate monitoring
- AI recommendations/auto-pausing
- provider/ESP matching

Empire should not compete by reproducing those screens.

## Differentiators now in the Ringleader branch

### 1. Deliverability Twin
Simulates the risk of a planned batch before release.
Uses current sending volume, bounce, complaint, deferral, authentication,
recipient verification and measured placement evidence.

### 2. Revenue-Aware Reputation Budget
Treats sender reputation/capacity as scarce capital.
Only already-approved, verified, unsuppressed opportunities are considered.
Higher predicted commercial value and conversation probability can receive capacity first.
It never expands the safety cap.

### 3. Recipient-MX Adaptive Pacing
Gmail, Outlook, Yahoo and other MX families have independent circuit breakers.
A destination-specific deferral does not require damaging every other healthy lane.

### 4. Canary Gate
A larger approved batch begins with a bounded canary.
Hard bounces, complaints, deferrals or poor measured seed placement stop expansion.

### 5. Reputation Blast-Radius Graph
Maps:
transport -> IP/pool -> DKIM selector -> domain -> mailbox -> campaign.
When one dependency degrades, Ringleader can identify every affected asset.

### 6. Provider Policy Registry
Vendor acceptable-use and sending policies are dated evidence.
A provider policy change can move a transport from permitted to hold without rewriting
Empire decision logic.

### 7. Sovereign Seed Transport Benchmark
Compare policy-compatible transports using only Empire-controlled seed recipients.
Measure inbox/spam/missing and latency before migrating real production traffic.

### 8. Commercial Outcome Feedback
Learn from positive replies, meetings, proposals, terms, revenue, negative replies,
opt-outs, bounces and complaints.
Do not optimize the core learning loop around tracking pixels or opens.

### 9. Deliverability Compiler
Compile an already-approved opportunity set into:
- sender assignments
- MX-specific capacity
- canary cohort
- bounded remainder
- explicit unallocated reasons

Compilation never authorizes sending. The existing Outbound Governor remains authoritative.

## Strategic principle

Other platforms optimize email activity.

Empire should optimize:

    VERIFIED COMMERCIAL VALUE
    --------------------------------
    REPUTATION RISK + DELIVERY RISK

subject to hard policy, consent/suppression, provider, authentication,
capacity and Founder approval constraints.
