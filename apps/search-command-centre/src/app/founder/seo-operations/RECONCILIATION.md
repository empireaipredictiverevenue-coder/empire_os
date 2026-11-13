# Source to protected release preflight

Flow: injected/read-only candidate source + compiled Next manifest + optional
loopback HTTP observations → deterministic JSON → original release owner.
No dashboard, service, queue, activation, file writes or outbound requests.

The pinned SHA256 table represents the **full seven file contents** at canonical
commit `19eb011ebf05d792bb7970414bd5f6f698c11634`, including prior canonical changes.
A candidate with only the SEO delta but different surrounding source is held;
reconcile differences with the original owner instead of weakening hashes.

Run from the repository root (all generated output stays in `/tmp`):

```bash
apps/search-command-centre/node_modules/.bin/tsc \
  --target es2022 --module commonjs --moduleResolution node --esModuleInterop \
  --strict --skipLibCheck --types node \
  --typeRoots apps/search-command-centre/node_modules/@types \
  --outDir /tmp/seo-reconciliation-check \
  apps/search-command-centre/src/app/founder/seo-operations/reconciliation*.ts
SEO_CANDIDATE_ROOT="$PWD/apps/search-command-centre" \
  node /tmp/seo-reconciliation-check/reconciliation-preflight.test.js
node /tmp/seo-reconciliation-check/reconciliation-cli.js \
  "$PWD/apps/search-command-centre" > /tmp/seo-reconciliation.json
# Explicit optional read-only live observation:
node /tmp/seo-reconciliation-check/reconciliation-cli.js \
  "$PWD/apps/search-command-centre" --probe-live > /tmp/seo-reconciliation-live.json
```

Exit 0 means structural candidate checks and live observations pass; exit 2
means HOLD. `productionRelease` always remains HOLD: this tool cannot prove
bundle/source build provenance, full protected route inventory, behavior parity,
SEO API data truth or deployment authority. Use a freshly built candidate and
retain the manifest digest with its build receipt. An existing `.next` manifest
can be stale; its existence is not a fresh build claim.

`reconcile` accepts injected source readers, observations, additional protected
routes and proposed route changes. The CLI probes only six fixed loopback routes;
additional inventory must be supplied by the release owner through the utility.
Any proposed change outside the SEO route holds. Any missing protected route
holds regardless of live status. Dynamic patterns cannot satisfy concrete route
invariants; Next route groups and parallel slots are normalized.

HTTP 200 is an HTTP observation, not proof of a route's intended behavior. SEO
markers are rendered heading IDs, not verified metric values. `data` remains
`unverified` even with both markers. No body, exception text, task contents,
credentials or personal fields are serialized. The optional probe uses GET,
127.0.0.1:3001 only, no redirects/cookies, 5-second timeout and 2 MiB body cap.
Network denial is unknown evidence, never inferred success.

The JSON handoff names the exact SEO patch commit, protected route requirements
(including Browser Operator), discrepancies and the original release owner.
The owner's actual v2r3 source is required; historical v2r2 cannot establish its
parity. This utility never reads protected source or writes a private release.

Current local rehearsal: six canonical files exact, `page.tsx` mismatch (the
canonical page also includes original revenue focus/canary integration absent
from this older owner branch); compiled Browser Operator route missing. These
are genuine HOLDs. They must not be repaired by overwriting protected routes or
editing another owner's Founder page/API files. Evidence JSON is emitted to
stdout for the Git/release-capable operator to archive in the existing owner
evidence path; this task's filesystem scope permits only owned source and `/tmp`.
