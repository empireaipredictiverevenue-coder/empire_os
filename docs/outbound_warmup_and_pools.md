# Empire Warm-up and Pooling

## Warm-up doctrine

Warm-up means gradually establishing reputation using legitimate traffic.
Empire does not use synthetic warm-up networks, fabricated replies, fake opens,
or reciprocal engagement schemes.

Ringleader controls the state machine:

NEW -> VERIFYING -> RAMPING -> ACTIVE
                    |          |
                    v          v
                THROTTLED -> RECOVERY
                    |
                    v
               QUARANTINED
                    |
                    v
                 RETIRED

A sender cannot enter RAMPING until:
- provider policy permits the traffic type
- DNS/authentication is verified
- suppression is known
- the sender identity is stable
- traffic is real
- the domain belongs to an approved pool

Volume is increased gradually and kept consistent.
Bounces, complaints, deferrals, auth failures, placement deterioration or sudden
volume spikes cause Ringleader to throttle or quarantine automatically.

## Pool types

### Domain pool
Stable domains grouped by traffic purpose.
Examples: transactional, relationship, prospecting, placement-test.
Do not rapidly rotate domains to escape reputation.

### Mailbox pool
Stable sender identities inside an approved domain.
Each mailbox has its own cap, history and health score.

### Transport/IP pool
Separate transport or IP reputation by traffic class.
Useful for migration and blast-radius control.
Do not churn IPs to bypass filtering.

### Recipient-MX pool
Queue/pacing buckets for Gmail, Outlook, Yahoo and other destination MX networks.
This lets Empire obey provider-specific backoff and SMTP deferral signals.

### Seed-placement pool
Mailboxes Empire controls for measuring Inbox/Junk/Missing.
Never use these mailboxes to create artificial engagement.

## Ringleader rules

- increase gradually only when health remains green
- no sudden bursts
- destination-specific deferrals immediately reduce that MX pool
- hard bounce affects recipient and sender health
- complaint affects sender/domain health immediately
- authentication failure freezes the domain pool
- placement degradation blocks scale-up
- recovering pools grow more slowly than new healthy pools
