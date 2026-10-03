# Search Intelligence Live Read Service V1

DIAGRAM: existing Search Intelligence modules -> canonical Search router -> loopback read/preview service -> internal product consumers.

ARCHITECTURE CONTRACT: reuse the canonical router and configured canonical repository. Bind only to 127.0.0.1. Preserve OBSERVE and execution_allowed=false. Do not expose commercial terms, publishing authority, outbound, payments, migrations, or synthetic evidence. Repository-backed capabilities remain unavailable when canonical configuration is unavailable.

WORKER ASSIGNMENT: deterministic bounded implementation because the shared Founder/public gateway paths are externally owned by the Digital Avatar / Recall workstream.

VERIFY: focused service and Search product tests, compile, diff check, systemd verify, loopback live probes, failed-unit check.
