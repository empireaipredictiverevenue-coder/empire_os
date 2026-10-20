# Empire AI — Brave Search free-credit metered transient worker
Date: 20 October 2026
Worktree: /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020

## Founder account ceiling
Founder's Brave dashboard usage limits show:
- Search: "Free credits only"
- Enabled column was not readable in the copied table.
Therefore the dashboard cap exists but activation must be verified visually.
Brave Search is $5 / 1000 requests and includes $5 monthly credit. Do not
equate this to entitlement to store search results.

## Why restricted
Brave Search standard API terms (updated 1 Sep 2026) prohibit storing,
caching, databases or derivative works of Search Results except transient
operational storage. Storage rights require a separate applicable plan.

Docs:
https://api-dashboard.search.brave.com/documentation/resources/terms-of-service
https://brave.com/search/api/

Our canonical Search Fabric caches provider responses and Buyer Scout
persists research seeds. The protected systemd drop-in
/etc/systemd/system/empire-buyer-acquisition-scout.service.d/
90-brave-search-rights-budget-hold.conf excludes BRAVE_API_KEY only from
the scheduled canonical Buyer Scout service. The founder installed the
drop-in and verified UnsetEnvironment=BRAVE_API_KEY. Keep it in place.

## New isolated worker, no scheduler
empire_os/a2a_brave_transient_budget_v1.py
- Atomic fcntl-protected local request counters.
- Hard internal caps: 100 requests in a UTC calendar month, 2 per UTC day.
- Every attempted request consumes internal allowance even if it fails.
- Stores only counter/date; no query, result, URL, snippet or buyer data.
- Rejects invalid ledger, symlink, clock rollback and over-limit.

scripts/run_a2a_brave_transient_search_20261020.py
- Dry-run is the normal verification path and uses zero provider calls.
- Explicit separate approval required to execute a single live request.
- Exactly one fixed Search API request: no retries, no redirects.
- Only 3 approved market presets: tampa_roofing, little_rock_hvac,
  nyc_general_contractors. No personal or unbounded search terms.
- Result titles, snippets and URLs are ephemeral inside the process.
- Only HTTP status, result count and local usage counters printed.
- No source caching, Buyer Scout/EmpireDB writes, outbound or AI training.
- The worker currently offers a temporary search operation/health lane,
  NOT persisted automatic company discovery, because storage rights have
  not been independently established.

## No paid execution has been activated
No additional live Brave request was sent by the new budget worker during
installation or validation. First dry-run printed 0/100 monthly and 0/2 daily.

Test:
cd /home/ubuntu/empire_worktrees/a2a_commercial_signal_mining_20261020
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B -m pytest -q  tests/test_a2a_brave_transient_budget_v1_20261020.py  tests/test_brave_preflight_response_safety_20261020.py

Dry-run:
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B  -m scripts.run_a2a_brave_transient_search_20261020  --market tampa_roofing --dry-run

To run a future ONE-REQUEST approved live diagnostic, an owner must invoke
the script through a root-managed transient systemd service with the existing
EnvironmentFile=/etc/empire_os.env, as in earlier approved preflight.
Never expose the key in CLI, Git, chats, logs or ordinary shell history.
No automated timer exists for this new worker.

## Remaining owner approvals
1. Verify "Enabled" for the account-level Free credits only usage limit.
2. Clarify rights before persisting Brave-discovered company domains or
   search-derived intelligence to CRM/Buyer Scout.
3. Conduct first-party, independently licensed / robots-permitted site
   inspection for candidate business evidence, and keep lawful source
   provenance. No browser/robots bypass.
4. Canonical Buyer Scout owner validates business identity, purchase intent,
   territory and duplicate/suppression states before commercial promotion.
5. Review mainline integration and avoid changing dirty production checkout.
