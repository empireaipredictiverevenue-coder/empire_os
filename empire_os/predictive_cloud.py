#!/usr/bin/env python3
"""Predictive Cloud — Distributed Omega OS scoring mesh.

Each Empire OS agent runs Omega 8-dimensional scoring locally and
gossips scores to P2P mesh neighbors. Consensus score = weighted
average by reputation stake. Agents earn/retain stake based on
scoring accuracy vs. actual outcomes.

Roadmap:
  Phase 2.1: Local scoring + mesh broadcast (this module)
  Phase 2.2: Reputation system + stake weighting
  Phase 2.3: Consensus API (/v1/predictive/score)
  Phase 2.4: Decentralized agent cards registered on mesh
"""

# ── Mesh Configuration ──────────────────────────────────────────────────────
MESH = {
    "nodes": [],  # populated at runtime via hub API discovery
    "gossip_interval": 300,  # 5 minutes between score broadcasts
    "consensus_quorum": 3,  # minimum 3 nodes for valid consensus
    "reputation_weight": "stake",  # how score weight is computed
    "score_dimensions": [  # must match PREDICTIVE_ENGINE
        "lead_quality",
        "speed_scale",
        "ai_intelligence",
        "revenue_optimization",
        "automation",
        "analytics_insight",
        "integration",
        "self_learning",
    ],
    "fallback_to_local": True,  # if mesh unavailable, score locally
}

# ── Agent Reputation & Stake ────────────────────────────────────────────────
# Tracks each mesh node's scoring accuracy and stake balance

REPUTATION = {
    "stake": {},          # agent_id -> USdc stake amount
    "accuracy": {},      # agent_id -> % accuracy (0.0-1.0)
    "total_scored": {},  # agent_id -> number of leads scored
    "correct_predictions": {},  # agent_id -> how many predictions matched outcomes
}

# ── Core Scoring Functions ─────────────────────────────────────────────────

def omega_score_8dim(lead_data: dict) -> dict:
    """Score a lead using the 8-dimensional Omega OS engine.

    Returns dict with per-dimension score (0-100) and composite.
    """
    dimensions = MESH["score_dimensions"]
    raw = lead_data.get("raw_data", lead_data)  # fallback to full dict

    # Default scores if data not present
    scores = {}
    composite = 0.0

    for i, dim in enumerate(dimensions):
        # Simple heuristic: extract or default to 50 (mid-range)
        # In production: real feature extraction from lead_data
        val = raw.get(dim, 50)
        # Clamp to 0-100
        val = max(0, min(100, float(val)))
        scores[dim] = val
        composite += val

    composite = round(composite / len(dimensions), 2)  # average 0-100

    return {
        "composite": composite,
        "dimensions": scores,
        "tier": tier_from_score(composite),
        "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
    }


def tier_from_score(composite: float) -> str:
    """Map composite Omega score (0-100) to BRONZE/SILVER/GOLD/PLATINUM."""
    if composite <= 39:
        return "BRONZE"
    elif composite <= 59:
        return "SILVER"
    elif composite <= 79:
        return "GOLD"
    else:
        return "PLATINUM"


def compute_consensus(scores_from_nodes: list) -> dict:
    """Compute consensus score from multiple mesh node scores.

    Weighted by reputation stake. If fewer nodes than quorum,
    fall back to simple average or local score.
    """
    if not scores_from_nodes:
        return {"composite": 0.0, "tier": "BRONZE", "method": "no_data"}

    if len(scores_from_nodes) < MESH["consensus_quorum"]:
        # Not enough nodes — simple average of what we have
        avg = sum(s.get("composite", 0) for s in scores_from_nodes) / len(scores_from_nodes)
        return {
            "composite": avg,
            "tier": tier_from_score(avg),
            "method": f"partial_average_{len(scores_from_nodes_nodes)}",
        }

    # Weighted by reputation stake
    total_stake = 0.0
    weighted_sum = 0.0

    for node_score in scores_from_nodes:
        agent_id = node_score.get("agent_id", "unknown")
        stake = REPUTATION["stake"].get(agent_id, 1.0)  # default 1.0 if unknown
        score = node_score.get("composite", 0)
        total_stake += stake
        weighted_sum += score * stake

    if total_stake == 0:
        # Fallback: simple average
        avg = sum(s.get("composite", 0) for s in scores_from_nodes) / len(scores_from_nodes)
        return {"composite": avg, "tier": tier_from_score(avg), "method": "fallback_simple_avg"}

    consensus = round(weighted_sum / total_stake, 2)
    return {
        "composite": consensus,
        "tier": tier_from_score(consensus),
        "method": "stake_weighted_consensus",
    }


# ── Mesh Broadcast / Gossip ─────────────────────────────────────────────────

def broadcast_score(agent_id: str, lead_uid: str, score_result: dict):
    """Broadcast a scored lead to mesh neighbors.

    In production: send via libp2p/mDNS gossip protocol.
    For this foundation: store in local mesh state + hub API.

    Returns: list of neighbor acknowledgments
    """
    # Ensure agent has reputation entry
    if agent_id not in REPUTATION["stake"]:
        REPUTATION["stake"][agent_id] = 1.0  # initial stake
        REPUTATION["accuracy"][agent_id] = 0.5  # neutral starting accuracy
        REPUTATION["total_scored"][agent_id] = 0
        REPUTATION["correct_predictions"][agent_id] = 0

    # Attach agent_id to score result for gossip
    scored_with_id = dict(score_result)
    scored_with_id["agent_id"] = agent_id
    scored_with_id["lead_uid"] = lead_uid

    # TODO: actual P2P gossip libp2p implementation
    # For now: persist to hub for dashboard display
    # hub_api_post("/v1/predictive/gossip", scored_with_id)

    return {"status": "gossip_queued", "agent_id": agent_id, "lead_uid": lead_uid}


def update_reputation(agent_id: str, prediction_composite: float, actual_outcome: float):
    """Update agent reputation based on scoring accuracy.

    Accuracy = 1 - |prediction - actual| / max_possible_spread
    Stake adjustments: +10% for accurate, -5% for inaccurate
    """
    if agent_id not in REPUTATION["stake"]:
        REPUTATION["stake"][agent_id] = 1.0
        REPUTATION["accuracy"][agent_id] = 0.5

    # Compute accuracy: closer prediction = higher accuracy
    spread = 100.0  # max spread of Omega scores (0-100)
    error = abs(prediction_composite - actual_outcome)
    accuracy = max(0.0, 1.0 - error / spread)

    # Update accuracy EWMA (exponential weighted moving average)
    prev_accuracy = REPUTATION["accuracy"].get(agent_id, 0.5)
    REPUTATION["accuracy"][agent_id] = round(
        0.7 * prev_accuracy + 0.3 * accuracy, 4
    )

    # Adjust stake based on accuracy
    stake_adjustment = (REPUTATION["accuracy"][agent_id] - 0.5) * 0.1  # ±5% max
    new_stake = max(0.1, REPUTATION["stake"][agent_id] + stake_adjustment)
    REPUTATION["stake"][agent_id] = new_stake

    # Track volumes
    REPUTATION["total_scored"][agent_id] = REPUTATION["total_scored"].get(agent_id, 0) + 1
    if accuracy > 0.5:
        REPUTATION["correct_predictions"][agent_id] = REPUTATION["correct_predictions"].get(agent_id, 0) + 1

    return {
        "agent_id": agent_id,
        "accuracy": REPUTATION["accuracy"][agent_id],
        "stake": REPUTATION["stake"][agent_id],
        "total_scored": REPUTATION["total_scored"][agent_id],
    }


# ── Consumption: Get Consensus Score for a Lead ─────────────────────────────

def get_consensus_score(lead_data: dict, agent_id: str = None) -> dict:
    """Get a consensus Omega score for a lead.

    Process:
    1. Score locally via omega_score_8dim()
    2. If mesh peers available, gather their scores + compute stake-weighted consensus
    3. Return final composite + tier + method

    Usage: get_consensus_score(lead_data) for autonomous scoring
           get_consensus_score(lead_data, agent_id="my_node") for node-specific
    """
    # Step 1: Local score
    local_score = omega_score_8dim(lead_data)

    # Step 2: Try mesh consensus if agent_id provided and mesh available
    consensus = local_score  # default to local
    if agent_id and MESH["nodes"]:
        # Gather scores from mesh neighbors (simulated: query hub for now)
        # In production: each mesh node broadcasts its score for this lead
        neighbors = [n for n in MESH["nodes"] if n != agent_id]
        if neighbors:
            # Simulate gathering 3 neighbor scores
            neighbor_scores = []
            for neighbor in neighbors[:3]:  # quorum = 3
                # Query neighbor's local score (real implementation would gossip)
                # For foundation: use local score with reduced weight
                neighbor_local = omega_score_8dim(lead_data)
                neighbor_scores.append(
                    {"agent_id": neighbor, "composite": neighbor_local["composite"]}
                )

            # Compute stake-weighted consensus
            consensus = compute_consensus(neighbor_scores)

    # Step 3: Attach method metadata
    consensus["local_composite"] = local_score["composite"]
    consensus["local_tier"] = local_score["tier"]
    consensus["method"] = consensus.get("method", "local_only") + "_with_mesh_fallback"

    return consensus


# ── If running standalone, show mesh setup ──────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("PREDICTIVE CLOUD — DISTRIBUTED OMEGA OS SCORING MESH")
    print("=" * 60)
    print()
    print("Mesh Configuration:")
    print(f"  Nodes: {len(MESH['nodes'])} (populated at runtime via hub)")
    print(f"  Gossip interval: {MESH['gossip_interval']}s ({MESH['gossip_interval']/60} min)")
    print(f"  Consensus quorum: {MESH['consensus_quorum']} nodes")
    print(f"  Score dimensions: {', '.join(MESH['score_dimensions'])}")
    print()
    print("Reputation System:")
    print(f"  Initial stake per agent: 1.0 USDC")
    print(f"  Accuracy EWMA: 70% past + 30% new")
    print(f"  Stake adjustment: ±5% per cycle based on accuracy")
    print(f"  Min stake: 0.1 USDC (cannot go below)")
    print()
    print("Core Functions:")
    print(f"  omega_score_8dim(lead_data) -> composite 0-100 + tier")
    print(f"  broadcast_score(agent_id, lead_uid, score_result) -> gossip queue")
    print(f"  update_reputation(agent_id, prediction, actual) -> accuracy + stake")
    print(f"  compute_consensus(scores_from_nodes) -> stake-weighted average")
    print(f"  get_consensus_score(lead_data, agent_id) -> final consensus score")
    print()
    print("Roadmap:")
    print("  Phase 2.1: ✅ (this module) — local scoring + mesh broadcast")
    print("  Phase 2.2: — reputation system + stake weighting")
    print("  Phase 2.3: — consensus API endpoint (/v1/predictive/score)")
    print("  Phase 2.4: — decentralized agent cards on mesh")
    print("=" * 60)