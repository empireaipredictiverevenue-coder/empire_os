"""Retired Astra hosted-token transport marker.

Astra is EmpireDB-only. Runtime transport is provided by
empire_os.outcome_role_transport.PostgresOutcomeRpc.
"""

RETIRED = True
CANONICAL_TRANSPORT = (
    "empire_os.outcome_role_transport.PostgresOutcomeRpc"
)
