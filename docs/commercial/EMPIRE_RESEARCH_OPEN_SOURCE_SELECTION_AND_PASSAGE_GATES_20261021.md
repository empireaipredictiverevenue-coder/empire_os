# Empire AI proprietary research — selective open-source decisions

21 October 2026. Owned isolated research branch. Dental UK/US first; six configured niches overall. No production publication or customer delivery.

## Verified this turn

- Existing local BeautifulSoup 4.15.0, MIT, is already installed. Reused it to extract 8 or fewer provenance-bound, short, source-page-only excerpts, capped at 165 chars/25 words, with SHA-256. No new package installed.
- Original US (Chicago) and GB (Birmingham/CMA) page runs produced 16 independently checksum-valid short passage anchors across 6 original pages (3+4+3 US, 2+2+2 GB); source-rights and original Research sign-off still false.
- Existing Search Fabric in the inspected process has BRAVE_API_KEY absent; independent reliable-search fallback is CIRCUIT_OPEN after 2 provider failures. A key may exist in another authorised setting, but none was inferred. Do not invent fresh search sources.
- 86 regression tests passed, including existing Search Fabric recovery tests, source-provenance and altered checksum refusal.

## Candidates ranked by utility, not popularity

1. BeautifulSoup 4 (MIT, already installed): ADOPTED in isolated source-passage harness. Do not add a second extraction system for simple HTML.
2. Crawl4AI (Apache-2.0; https://github.com/unclecode/crawl4ai): PREFERRED next *isolated proof-of-concept* only for complex JavaScript websites that the bounded original-source fetcher cannot extract. Pin to a patched version, audit recent SSRF/file-writing advisories, run as separate loopback sandbox with a strict domain allowlist, no unknown browser actions or secrets. Measure extraction fidelity, runtime cost and page failure rate against the 6 original pages before deciding to integrate.
3. Scrapling (BSD-3; https://github.com/D4Vinci/Scrapling): optional ordinary HTML selector/extraction fallback; lower priority. Do not use stealth/antibot bypass modules or account impersonation.
4. SearXNG (AGPL-3.0; https://github.com/searxng/searxng): optional search metasearch fallback, NOT first. Underlying providers still impose throttles; if modified/network deployed, verify network copyleft requirements before product integration.
5. Vane (MIT; https://github.com/ItzCrazyKns/Vane): reusable speed/balanced/quality and cited-answer concepts, already piloted. Do not clone its complete product stack over EmpireOS.
6. OpenManus (MIT; https://github.com/FoundationAgents/OpenManus): step planner and receipt concepts, already reused; keep shell and browser actions strictly bound and approval separate.
7. Tongyi DeepResearch (Apache-2.0 repo, 30.5B total parameter model; https://github.com/Alibaba-NLP/DeepResearch): model research reference, not drop-in given local 1.5B inference quality/compute.
8. Haystack (Apache-2.0; https://github.com/deepset-ai/haystack): capable but duplicates existing orchestration; defer.
9. Langfuse OSS (MIT core, enterprise exceptions; https://github.com/langfuse/langfuse): later evaluation/trace layer if existing EmpireOS research telemetry and SkillForge cannot provide the needed source precision, latency and editorial feedback. Disable or review telemetry before considering private data.

## Specific execution gates

First repair the existing Search Fabric/Brave provider configuration through approved secret ownership and verify genuinely fresh US/GB results, without auto-admitting external search snippets.
Second demand a citation anchor, quote integrity, negation and category/jurisdiction checks for model suggestions; quoted publisher words are not independently proven facts.
Third run pinned Crawl4AI in an isolated sandbox against existing six approved URLs and a separately verified JS-heavy Research-approved site, only to close measured extraction misses.
Fourth reconcile the original five stale-snapshot Research queue receipts through newly versioned current-source tasks and independent authenticated editorial acceptance; never rewrite old DONE evidence or forge approval.
Fifth transfer vetted source-citation research methods to roofing, solar, HVAC, legal and property, not US dental evidence itself.

Commercial protocol remains research -> useful editorially approved insight -> relationship -> real buyer question -> defined scope -> proposal only when asked/qualified. No automatic send, CRM write, funds or source-rights grant.
