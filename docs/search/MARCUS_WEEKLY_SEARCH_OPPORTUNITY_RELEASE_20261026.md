# Empire AI — operational Keyword → Evidence → Opportunity weekly integration

**Release date:** 26 October 2026. **Existing owner:** `empire-seo-two-page-gsc-weekly.service`. **No new daemon, timer, PostgreSQL database, third-party API account or browser automation.**

## Live source and first production-data dry run

An actual GET to the existing `127.0.0.1:8771/v1/search/search-console/observations` returns Google Search Console query/page observations for the owned `sc-domain:empire-ai.co.uk` property. The 17–23 October finalized window currently returned **two query/page rows**. This is a private first-party sample, not the true total keyword demand.

A complete one-shot execution of the new weekly review through the isolated worktree wrote one **immutable mode-0600** original-source receipt into the **existing** owner-owned SEO weekly folder:

`/home/ubuntu/empire_releases/seo_weekly_gsc_two_page_20261022/weekly_keyword_intent_2026-10-26.json`

SHA-256 `1a73bafff0ebfe343f7b3850a998bf3a619e89ddf66a3f3205bc4d2bb9977679`; folder/receipt are owner-only. This initial report generated 27 roofing, 23 heat-pump, 23 SaaS revenue assessment and 15 TAM phrase hypotheses with **zero exact owned-GSC matches** in this *specific* 17–23 October window. It performed **one** reused first-party GSC GET and zero new search-fabric, paid provider or outbound calls.

**Pilot correction:** The initial TAM report included clumsy trigger modifiers appended to a whole natural-language question. The generator is now regression-tested to preserve long buyer questions *verbatim* as one original query, not 15 spammy variations. The original first receipt remains immutable and is not rewritten. On subsequent weekly runs, TAM will contribute one research idea, leaving the other research sectors and source evidence unchanged.

## Normal operation

The EXISTING `scripts/report_weekly_two_page_gsc_20261022.py --write-private` script owns weekly reporting. After successfully saving the existing two-page GSC receipt it invokes `empire_os.weekly_keyword_intent_review.run_weekly_keyword_intent_review` using the *same* as-of date, the already-authorized local API and same private receipt folder. Nothing is scheduled separately. The current systemd timer runs on **Monday at 10:00 Europe/London** with existing timeout, non-root user and filesystem hardening.

One local query/page GET per cycle is shared across four internally maintained research sectors. No numeric economic rankings or fake market search volume: priority 1 = exact owned first-party query match (if one exists), then commercial-intent hypothesis, then educational research. All decisions remain research-only, with no content publishing, indexation, lead contact or money movement.

The original two-page report remains valid if the optional keyword add-on fails. The JSON returned to the scheduled observer reports `HELD_WEEKLY_KEYWORD_REVIEW_NOT_ARCHIVED` with only an error type, making failure visible without overwriting or misreporting the canonical GSC weekly receipt.

## Verification before release

- Dedicated original keyword bridge, GSC and SERP source evidence, query triage and original weekly owner extension tests must pass.
- Verify `/etc/systemd/system/empire-seo-two-page-gsc-weekly.service` retains `User=ubuntu`, the original `ExecStart`, strict filesystem protection and existing allowed private receipt directory.
- Verify `/srv/empire_os` scoped files are clean and preserve all unrelated dirty files.
- No new timer or restart of the running Search Intelligence API; Python modules are loaded at next weekly `Type=oneshot` invocation.
- Run `scripts.review_public_intent_offer_method_20261025` once in production *without write flags* to prove the correct original source and safe query-triage outputs.
- Next automatic weekly run: Monday 2 November 2026, roughly 10:00 UK, dependent on existing timer health. Do not claim that future run has happened yet.
- No external SERP search or keyword volume provider has been added to the weekly timer. Those remain explicit future provenance checks.

## Operating command (read only)

```bash
cd /srv/empire_os
PYTHONPATH=. .venv/bin/python -B -m scripts.review_public_intent_offer_method_20261025 \
  --market us-commercial-roofing \
  --seed 'commercial roof repair' \
  --icp commercial-roofing-operator \
  --buyer-problem 'Evaluate roof repair versus replacement' \
  --gsc-start 2026-10-17 \
  --gsc-end 2026-10-23
```

Financial truth and conversion remain separate: raw searches ≠ relevant buyer ≠ accepted deal ≠ realised paid revenue. The software does not make these claims.

## Additional original GSC query discovery bridge (26 October; source-only enhancement)

The October 26 original weekly owner research module was enhanced in its existing Marcus feature branch so real first-party GSC queries are no longer silently overlooked when none matches generated seed phrases. There is NO second Google GET, search API, scheduler, keyword DB or editorial producer.

- In the same original bounded GSC observation packet, all four market candidate sets preserve the *same* unmatched genuine GSC query/page rows using exact deduplication across markets. Queries matching any original market set are excluded from the unmatched list.
- The existing Search Intelligence semantic_opportunity_review module receives only the original query text plus exact GSC evidence ref, and labels intent and sector as *heuristic*. Up to 12 owned-only query/page candidates are included in the private 0600 weekly research receipt; bounded raw evidence counts remain visible. Email-like and oversize query phrases are excluded from this preview to reduce accidental sensitive disclosures.
- No generated idea becomes a Google ranking, proven consumer, volume or keyword difficulty. Both source unavailable and confidential/sensitive query redaction remain explicit.
- A fresh read-only check of 17–23 Oct GSC on Oct 26 returned two real query/page rows, zero exact matches to the four seeds and **two unmatched actual query/page rows** preserved. Both semantic analyses abstained UNKNOWN_INTENT / UNKNOWN_NO_EXPLICIT_SECTOR_EVIDENCE. This is a positive evidence-custody improvement, not a discovery of two commercially attractive opportunities.
- Existing combined Marcus/semantic test suite: 91 passed. No published page, autonomous outbound, payment, paid search API, Jev provider call or production DB write.
- Feature branch alone: retain the installed production weekly owner and coordinate with Search Intelligence owner before merging this isolated minimal module/test/document change. The production weekly GSC script is also edited by another agent and was **not** changed here.
