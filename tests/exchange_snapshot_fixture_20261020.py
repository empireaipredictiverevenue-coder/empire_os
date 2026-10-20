"""Small synthetic canonical snapshot for isolated Exchange integration tests.

No customer record, payment, buyer contact or network call is included.
Unlike previous integration history this fixture does not import private
founder API routes or link to a live buyer/CRM.
"""
from datetime import datetime,timezone

NOW=datetime(2026,10,19,13,35,tzinfo=timezone.utc)


def fixture():
    def row(identity,state):
        return {
            "prospect_id":identity,"state":state,
            "niche_family":"solar","metro":"London",
            "corridor_key":"corridor:v1:solar:london:qualified_lead:lead",
            "candidate_count":0,
            "empire_owned":state!="allocated",
        }
    return {
        "schema_version":"empire.commercial_exchange_snapshot.v1",
        "mode":"OBSERVE",
        "observed_at":NOW.isoformat(),
        "source":"canonical_empiredb_projection",
        "canonical_backend":"empiredb",
        "execution_authority":"none",
        "automatic_external_delivery":False,
        "inventory":[
            row("prospect-synthetic-1","blocked_missing_evidence"),
            row("prospect-synthetic-2","overflow_no_capacity"),
            row("prospect-synthetic-3","allocation_candidate"),
            row("prospect-synthetic-4","allocated"),
        ],
        "inventory_count":4,
        "inventory_state_counts":{
            "blocked_missing_evidence":1,"overflow_no_capacity":1,
            "allocation_candidate":1,"allocated":1,
        },
        "allocation_candidate_count":1,
        "overflow_count":1,
        "blocked_missing_evidence_count":1,
        "allocated_count":1,
        "buyer_seats":[{
            "buyer_id":"synthetic-buyer-1",
            "buyer_name":"Synthetic account",
            "seat_state":"active_capacity",
            "remaining_capacity":1,
        }],
        "buyer_seat_count":1,
        "seat_state_counts":{"active_capacity":1},
    }
