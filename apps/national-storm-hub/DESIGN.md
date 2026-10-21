# National Storm Hub — Impeccable-informed design system

Design reference: existing Hermes optional skill catalogue entry at /home/ubuntu/.hermes/hermes-agent/optional-skills/creative/impeccable/SKILL.md (metadata stub, NOT full installed skill). Upstream: pbakaus/impeccable (Apache-2.0). Not approved in Empire SkillForge; reference its public design concepts, never auto-load or run third-party hooks.

## Direction
A premium meteorological observatory meets calm public-service journalism: deep navy, electric cyan information details and sparing warm gold. Existing Manrope display and DM Sans body typography. Typography and source provenance before decorative cards. Cinematic graphic globe is explicitly illustrative; no implied live storm positions.

## Quality passes
- CRITIQUE: prioritize ZIP lookup, Alerts, Predictor and official source.
- POLISH: meaningful type and whitespace, less competing microcopy, clear primary and secondary actions.
- HARDEN: loading/unavailable/zero/invalid ZIP all visually distinct; no unsupported reassurance.
- ADAPT: working mobile nav, 44px touch targets, readable 320px, respects zoom.
- AUDIT: verify keyboard, semantic labels, reduced motion, actual source dates and HTTPS.
- No claims of screenshot testing if no verified browser image available.

Don't create a second framework, alert API, finance reader, CSS toolkit, skill approval or daemon. Work on existing Next.js app and verify build/tests before any guarded live release.

## Browser audit — confirmed 2026-10-21

- Chrome headless rendered homepage at 1440x950 with zero client-side JavaScript exceptions.
- Chrome DevTools mobile emulation at 390x844: innerWidth=390, scrollWidth=390, navigation collapsed correctly, hero headline/search/actions visibly fit and remain readable.
- Actual browser verified /alerts and /predictor?zip=75201 without a client error.
- A real browser failure was discovered in all three consumer pages: Intl.DateTimeFormat combined dateStyle/timeStyle with timeZoneName, which Chromium and Node rejected. Refactored to shared lib/weather-time.js using supported year/month/day/hour/minute/timeZoneName fields and explicit unknown-time fallback; regression-tested.
- Corrected mobile intrinsic grid track sizing and separated hero CTA links to avoid content clipping behind overflow:hidden.
- 20 National Storm Hub tests passed; Next production build succeeded; 19 SkillForge routing/trust tests previously passed.
- Preview remains loopback-only on EmpireOS port 3149. No public domain or production service change occurred in this audit.
