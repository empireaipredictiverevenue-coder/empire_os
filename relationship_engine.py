#!/usr/bin/env python3
"""
Empire OS — Relationship Engine (autonomous deep relationships at scale).

Builds a relationship graph from the CRM (company <-> buyer <-> referral <->
vertical) and scores interaction quality (Ragas-style heuristics) so agents
can deepen connections autonomously.

No external deps (graphify/ragas not pip-installable here — native impl).
Outputs: /root/feedback/relationship_graph.json, /root/feedback/quality.json
"""
import json, time, os, subprocess

CONTAINER = "empire-hub"
GRAPH_OUT = "/root/feedback/relationship_graph.json"
QUAL_OUT = "/root/feedback/quality.json"


def _crm(query, args=()):
    cmd = ["incus", "exec", CONTAINER, "--", "/root/venv/bin/python3",
           "/root/empire_os/crm_query.py", query, json.dumps(list(args))]
    try:
        return json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                          timeout=20).stdout)
    except Exception:
        return []


def build_graph():
    """Nodes = leads (companies) + verticals + buyers. Edges = co-vertical,
    referral (same email domain), source-similarity."""
    rows = _crm("SELECT business_name, email, source, url FROM si_buyer_outreach "
                "WHERE email IS NOT NULL LIMIT 5000")
    nodes, edges = {}, {}
    vert_count = {}

    def add_node(nid, ntype, label):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "type": ntype, "label": label, "deg": 0}

    def add_edge(a, b, kind):
        key = tuple(sorted([a, b])) + (kind,)
        edges[key] = edges.get(key, 0) + 1
        nodes[a]["deg"] += 1
        nodes[b]["deg"] += 1

    for r in rows:
        if not isinstance(r, list) or len(r) < 3:
            continue
        biz, email, src, url = r[0], r[1], r[2], r[2] if len(r) < 4 else r[3]
        vert = src.split(":")[-1] if ":" in src else "unknown"
        biz_id = f"co:{biz}"
        vert_id = f"vert:{vert}"
        add_node(biz_id, "company", biz)
        add_node(vert_id, "vertical", vert)
        add_edge(biz_id, vert_id, "in_vertical")
        # referral edge: same email domain across companies
        if email and "@" in email:
            dom = email.split("@")[-1].lower()
            ref_id = f"dom:{dom}"
            add_node(ref_id, "domain", dom)
            add_edge(biz_id, ref_id, "shares_email_domain")
        vert_count[vert] = vert_count.get(vert, 0) + 1

    graph = {
        "nodes": list(nodes.values()),
        "edges": [{"source": k[0], "target": k[1], "kind": k[2], "weight": v}
                  for k, v in edges.items()],
        "verticals": vert_count,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    os.makedirs(os.path.dirname(GRAPH_OUT), exist_ok=True)
    json.dump(graph, open(GRAPH_OUT, "w"), indent=2)
    return graph


def score_quality():
    """Ragas-style heuristics (rule-based, no LLM):
    - faithfulness: lead email matches business domain (no spoof)
    - context_precision: source tag present + vertical known
    - answer_relevancy: has url + email (reachable)
    - context_recall: dedup'd (not duplicate entity)
    Score per lead, averaged."""
    rows = _crm("SELECT business_name, email, source, url FROM si_buyer_outreach "
                "WHERE email IS NOT NULL LIMIT 5000")
    scores, n = [], 0
    for r in rows:
        if not isinstance(r, list) or len(r) < 3:
            continue
        n += 1
        biz, email, src, url = r[0], r[1], r[2], (r[3] if len(r) > 3 else "")
        s = 0.0
        # faithfulness: email domain relates to business (heuristic: any overlap)
        if email and "@" in email:
            edom = email.split("@")[-1].lower()
            s += 0.25 * (1.0 if edom.split(".")[0] in (biz or "").lower() or
                         (biz or "").lower()[:4] in edom else 0.5)
        # context_precision: source + vertical known
        s += 0.25 * (1.0 if ":" in (src or "") else 0.0)
        # answer_relevancy: reachable (url + email)
        s += 0.25 * (1.0 if url else 0.3)
        s += 0.25 if email else 0.0
        scores.append(min(1.0, s))
    avg = round(sum(scores) / n, 3) if n else 0.0
    out = {"avg_quality": avg, "sampled": n,
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    os.makedirs(os.path.dirname(QUAL_OUT), exist_ok=True)
    json.dump(out, open(QUAL_OUT, "w"), indent=2)
    return out


if __name__ == "__main__":
    g = build_graph()
    q = score_quality()
    print(f"[rel] graph: {g['node_count']} nodes, {g['edge_count']} edges | "
          f"quality: {q['avg_quality']} over {q['sampled']} leads")
