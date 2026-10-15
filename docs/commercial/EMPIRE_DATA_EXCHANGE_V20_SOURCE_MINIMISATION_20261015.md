# Empire Data Exchange V20 — Source-Input Minimisation

**Mode:** OBSERVE only. **Date:** 15 October 2026.

## Product outcome

Live Planning Data Brownfield Land responses contained a wider raw
field surface than Empire needed for the canonical source projection.
A bounded live V19 audit observed **59 raw field occurrences** over the
three fixed official entity responses, including **35 occurrences
outside the eight approved source input keys** and **6 potentially
sensitive key-name occurrences**. These are aggregate key counts, not
the number of personal records or proof that the raw data is or is not
personal information.

V20 hardens the existing first-party source transport:

- Existing `fetch_official_json` remains bounded to 200,000 bytes,
  HTTPS, exact official Planning Data hostname and no redirects.
- URLs must match the exact numeric source path
  `/entity/<positive integer>.json` shape; no arbitrary paths,
  credentials, queries, fragments or alternative hosts.
- New `fetch_projected_official_json` calls the same reviewed HTTP
  reader and returns ONLY the eight official source input keys:
  `entity`, `dataset`, `quality`, `organisation-entity`,
  `end-date`, `planning-permission-status`, `hectares`,
  `entry-date`.
- The existing V15 custody capture, V16 source preview and bounded
  public probe now use that projection as the DEFAULT input to the
  existing normalizer. Synthetic test dependency injection remains.
- The existing V19 raw-key audit deliberately still calls the raw
  read function, and shares the exact same constant for the
  projected-source allowlist. It prints only aggregate counts and
  never source values or keys.
- The new filter does not change what the existing normalizer
  stores as canonical records. Controlled tests compare whole
  snapshots and their exact V15 canonical snapshot/chain SHA256
  between old raw-input and new projected-input paths.

## Boundary of the privacy guarantee

The HTTP response still exists transiently as raw bytes and a decoded
full JSON object within the source fetcher, before projection.
The change restricts the **data handed to the source normalizer**
and narrows the code surface in which extra data travels; it is
not proof of complete raw-response memory erasure, actual presence
or absence of personal data, a compliant privacy regime or a human
rights sign-off.

Therefore V18/V19 review controls continue to state
`raw_source_response_privacy_review_status=NOT_PERFORMED`,
no confirmed source-field rights clearance and no customer release.

## Verified test and live result

- 37 focused source minimization, V15 custody operator and V19
  source-key audit tests passed.
- Disposable **real PostgreSQL** custody gauntlet passed, including
  role restrictions, replay no-op, V16 24-hour write gate and
  production DB isolation.
- Live official-source-only V16 probe checked all **three pinned
  records** using the minimized path with `database_writes=false`.
- Live V19 raw-key audit returned its baseline aggregate
  3 responses / 59 raw key occurrences / 35 excluded occurrences /
  6 potentially sensitive key-name occurrences, with no raw
  values printed.
- All commercial activation flags stay false, no migrations,
  timers, new DB connections, outreach or payment execution.

## Next real observation

The existing V16 manual follow-up is eligible **no earlier than**
`2026-10-16T08:53:59.532101+00:00` (09:53:59 BST).
That capture requires separate founder approval as already
implemented and should be done only once after the gate is open.
V20 does NOT execute it.
