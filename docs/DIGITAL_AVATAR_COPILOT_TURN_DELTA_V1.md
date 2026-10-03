# Empire Digital Avatar — Copilot Turn Delta V1

Date: 2026-10-02
Status: HUMAN-APPROVAL FOUNDATION / OBSERVE-ONLY

## Purpose

Prepare the exact utterance the Digital Avatar wants to make without granting
speech authority.

A turn must be grounded before it can be presented for human approval.
Material claims carry a truth class and evidence refs. A commercial-close turn
must also pass the delegated commercial authority policy.

## Flow

LIVE MEETING STATE -> STRATEGY -> DRAFT TURN -> CLAIM/EVIDENCE REVIEW
-> COMMERCIAL AUTHORITY REVIEW (when applicable)
-> READY FOR HUMAN APPROVAL -> [future speech adapter]

V1 ends before speech. Human approval is a separate future promotion gate.

## Truth and safety

- OBSERVED: directly supported by meeting/provider or business evidence.
- VERIFIED: backed by approved canonical commercial evidence.
- INFERRED: interpretation based on referenced evidence.
- FORECAST: predictive output based on referenced model evidence.

No material claim without evidence may be presented as approval-ready.
No custom terms or out-of-policy close may be approval-ready.
No turn can execute speech, chat, payment, contract acceptance or funds movement.


## 2026-10-02 governed speech extension

The original V1 boundary remains the default: preparing a grounded turn does not
grant speech authority. A new separate, explicit one-turn promotion path has
been prepared for future live COPILOT use.

Revised flow:

```text
PRIVATE GROUNDED DRAFT
-> HUMAN REVIEW
-> EXACT TEXT HASH APPROVAL
-> VOICE RENDER
-> AUDIO HASH / BYTE / SAMPLE-RATE EVIDENCE
-> ONE-TURN TRANSMISSION TICKET
-> CLAIM TICKET
-> LOOPBACK PRESENCE PUSH
-> BROWSER PLAYBACK ACK
-> FINALIZE COMPLETED OR RECONCILIATION_REQUIRED
```

The one-turn ticket is not general speech authority. It is bound to one meeting,
one avatar, one Recall bot, one exact approved text fingerprint and one rendered
audio fingerprint. It is short-lived and one-use.

Browser Presence cannot request speech, mint a ticket, alter approved text or
obtain commercial authority. The browser only accepts server-pushed approved PCM
and acknowledges playback. Raw rendered PCM is not persisted by this path.

A browser playback acknowledgement proves the Presence webpage completed local
playback; it does not by itself prove the remote meeting participant heard the
audio. Meeting-side delivery remains a separate live verification requirement.

### Current status

Engineering proof is complete in the server worktree, including deterministic
replay rejection, timeout reconciliation, authority-negative tests and adjacent
speech/Presence regressions. Production speech remains inactive until the live
promotion gates in the master checklist are satisfied.

No COPILOT speech path grants contract acceptance, payment, funds movement,
commercial truth write or revenue-recognition authority.
