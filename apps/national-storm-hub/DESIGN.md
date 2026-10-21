# National Storm Hub — Impeccable-informed design system

Design reference: existing Hermes optional skill catalogue entry at /home/ubuntu/.hermes/hermes-agent/optional-skills/creative/impeccable/SKILL.md (metadata stub, NOT full installed skill). Upstream: pbakaus/impeccable (Apache-2.0). Not approved in Empire SkillForge; reference its public design concepts, never auto-load or run third-party hooks.

## Direction
**Private comparative design candidate:** Signal Noir (default) versus Command Red (more intense). Premium meteorological observatory meets a restrained emergency-response identity: graphite near-black, vivid emergency red for selected action and sourced severe-warning hierarchy, warm safety yellow for caution and key source details, and bright white editorial typography. Existing Manrope display and DM Sans body typography remain unchanged. Typography, truth/provenance and conversion clarity come before decorative cards. The cinematic conceptual globe is illustrative; it must never imply verified live storm positions.

Research-to-design references and Jack Roberts workflow are recorded in `DESIGN_REFERENCES_JACK_20261021.md`. Actual Empire Design Studio instructions already exist in `/home/ubuntu/empire_worktrees/empire_design_studio_20261018/empire_os/skills_library/skills/empire-design-studio/SKILL.md` and are **candidate guidance, not an approved runtime skill**.

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

## Immersive sliding experience — 2026-10-21

The homepage now has an independently coded, genuinely interactive 3D Stormfront Array **instead of a globe**. The intent is atmospheric data-art, not a storm observation:
- Three hero stories: read official forecast and source-limited predictor; check official active alerts; prepare a browser-local homeowner Storm Passport.
- Autoplay only where reduced motion is not requested, pauses on hover/focus and stops on user interaction. Text remains visible without WebGL.
- Separate editable hazard-guide slider beneath regional hubs, never an inferred hazard or damage verdict.
- Desktop pointer tilt and subtle scroll parallax on a native Three.js terrain mesh and animated ribbon groups; no remote content or synthetic customer event.
- At narrow widths or with reduced motion, a decorative CSS terrain-and-wave fallback replaces GPU rendering. Buttons, source links and ZIP input remain functional.
- Safety invariant: 3D art markers are **not geolocated reports**. To create a real Atlas, use authenticated official geometry with issue times, coverage and source provenance.
- Proof gate: Chrome viewport audits at 1440/820/390/320, real slider clicks, AJAX endpoints, reduced-motion fallback, WebGL detection, healthy server and 401 private founder finance route. Unit tests alone are insufficient.
