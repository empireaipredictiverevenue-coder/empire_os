# Empire Ops Bridge Control Plane

This branch is a transport queue for authenticated GitHub writers.

Requests live at:

`bridge/requests/<32-lowercase-hex-request-id>.json`

EmpireOS fetches this branch into a remote-tracking ref only; it never checks
the branch out into the production worktree.

Request schema:

```json
{
  "schema_version": "empire.ops_bridge.request.v1",
  "request_id": "0123456789abcdef0123456789abcdef",
  "operation": "repo_status",
  "arguments": {},
  "expires_at": "2026-10-05T12:00:00+00:00",
  "requested_by": "chatgpt-github-connector",
  "result_certificate_pem": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----\n"
}
```

Allowed operations are intentionally bounded to repository engineering,
verification, service status and Founder Directive intake. There is no
arbitrary shell, database mutation, outbound send, payment action, production
service-control execution, or authority expansion.

Results are written only as encrypted CMS payloads under EmpireOS runtime and
are exposed by request id through the ciphertext-only public result endpoint.
