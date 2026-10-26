# EmpireOS — existing AEO market guides to existing commercial B2B enquiry

26 Oct 2026. Original AEO generator and three already-published market guides only.

Verified original Search Intelligence growth action review suggested eight market/research routes as two-hop commercial-form paths. Live inspection established five original research campaign pages ALREADY expose their own first-party research enquiry form with reply email, research question and a non-marketing privacy notice. Adding generic duplicate forms or outbound CTA schemes there is not a warranted fix. The three AEO guides do not have direct B2B request actions and currently go to the homepage. Their original generator was reproduced byte-for-byte against the three public served HTML files; a minimal, exclusively scoped addition is appropriate.

Three exact routes:
- /aeo/general_contractor/NYC/
- /aeo/hvac/DFW/
- /aeo/roofing/DFW/

Source: scripts/aeo_metro_gen.py, original AEO generator, adds exactly one direct /commercial nonbinding business assessment link in the existing footer actions. Keeps all 205+ other generator outputs byte-for-byte unchanged and the existing DFW roofing qualification link. No mass regeneration or doorway rollout.

Delivery: source patch only + guarded three-live-page HTML swap via scripts/release_guarded_three_aeo_commercial_links_20261026.py. Public pre- and posthash must match source and approved candidate exactly. Existing live H1/canonical/content and anchored buyer-route selection remain unchanged except three inserted links. Owner preimages under /home/ubuntu/empire_releases/seo_aeo_direct_commercial_bridge_20261026_v1/ with rollback capability.

This does not create a homeowner form, fabricate leads, authorise affiliate payouts, manipulate link authority, send emails, or claim visits/revenue. New link is a transparent existing nonbinding B2B page. Do not treat direct-link availability as a conversion or paid event.

The existing SEO queue's five research-page two-hop candidate flags are NOT proofs of missing buyer action, because those pages contain existing research enquiry forms. Original buyer-journey analyzer may separately be enhanced to distinguish research-specific enquiry forms from the platform-wide B2B commercial form, rather than suppressing all research editorial findings blindly.

## Actual gateway hash-release discovery and corrected activation

An initial static-file-only overlay was rejected by the original public AEO gateway because published AEO pages are hash-gated: original aeo_release.load_release validates the current page against the recovery snapshot and approved root-owned release manifest. All three original HTML files were successfully rolled back and public HTTP 200 was verified. This is a correct safety hold, not a reason to bypass the publisher.

Corrected release candidate: /home/ubuntu/empire_releases/seo_aeo_governed_three_cta_20261026_v2/. Original build_aeo_recovery_census produced a 210-asset evidence snapshot with exactly 3 changed and 207 unchanged content hashes, zero added risk flags. Original build_release_manifest and load_release accepted exactly three original market guide pages with the current normalized content hashes and original plus 26 Oct founder evidence references. The original generator outputs byte-identical HTML candidate files.

Corrected activation: scripts/activate_original_three_aeo_b2b_links_20261026.py. Requires exact root-owned existing manifest/source hashes, validates all 210 live and source files, pre-stages original release objects, preserves backups and uid/gid/mode, updates exactly the 3 runtime pages, 3 generation snapshot pages, recovery and root-owned release manifest, and checks original release validator plus public HTTPS page bytes. On failure restores all changed files. No gateway restart, new page, paid link, API indexing request, DB write, service or outbound message. Root operator must explicitly activate this staged candidate: source staging is not a live publish.
