"""First-party Market Knowledge Graph projection over existing EmpireOS sources.

No graph database or second truth store. Provenance-preserving public research
relationships, approved scenario LESSONS, current-source health and data
products. Unverified public discussion is not buying intent or sales evidence.

Raw user content, author IDs, CRM data, chat transcripts and URLs are NEVER
published in graph/readout. Scoped private conversations cannot be imported.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit
import json
import re

from empire_os.icp_intent_source_atlas import SOURCES
from empire_os.community_intent_learning import SCHEMA as LEARNING_SCHEMA, source_id
from empire_os.intelligence_data_products import DATA_PRODUCTS
from empire_os.pain_solution_engine import SOLUTION_MAP

SCHEMA = "empire.flagship.market_knowledge_graph.v1"
MAX_OBSERVATIONS = 100
MAX_EXAMPLES = 80
MAX_BYTES = 450_000
OBS_AGE = timedelta(days=14)
LEARNING_AGE = timedelta(days=7)
EXAMPLE_LESSONS = frozenset({
    "ASK_FOR_ORIGINAL_BUYING_BRIEF",
    "VERIFY_SERVICE_AREA",
    "VERIFY_UNIT_PRICE_AND_MARGIN",
    "VERIFY_DELIVERY_CAPACITY",
    "EXPLAIN_UNKNOWN_VS_ZERO",
    "COMPARE_ALTERNATIVE_CHANNELS",
    "ASK_FOR_FULFILMENT_ACCEPTANCE",
})
LESSON_TOPIC = {
    "ASK_FOR_ORIGINAL_BUYING_BRIEF": "lead_generation",
    "VERIFY_SERVICE_AREA": "lead_generation",
    "VERIFY_UNIT_PRICE_AND_MARGIN": "sales_conversion",
    "VERIFY_DELIVERY_CAPACITY": "sales_conversion",
    "EXPLAIN_UNKNOWN_VS_ZERO": "data_intelligence",
    "COMPARE_ALTERNATIVE_CHANNELS": "search_visibility",
    "ASK_FOR_FULFILMENT_ACCEPTANCE": "sales_conversion",
}
SAFE_ID = re.compile(r"^[a-z][a-z0-9_]{2,75}$")
HEX = re.compile(r"^[0-9a-f]{64}$")


def _time(value: str) -> datetime:
    if not isinstance(value, str) or len(value) > 48:
        raise ValueError("invalid source time")
    try:
        out = datetime.fromisoformat(value.replace("Z","+00:00"))
    except ValueError as exc:
        raise ValueError("invalid source time") from exc
    if out.utcoffset() is None:
        raise ValueError("timezone-aware evidence required")
    return out.astimezone(timezone.utc)


def _hash(*fields: str) -> str:
    return sha256("|".join(fields).encode()).hexdigest()


def _read(root: Path, relative: str, max_bytes: int) -> dict[str, Any] | None:
    base = Path(root).resolve()
    file = base / relative
    if file.is_symlink() or file.parent.is_symlink() or not file.is_file():
        return None
    try:
        if not 0 < file.stat().st_size <= max_bytes:
            return None
        value = json.loads(file.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (ValueError, OSError, UnicodeError):
        return None


def _source_for_observation(obs: Mapping[str, Any], atlas: Mapping[str, Any]) -> str | None:
    raw = obs.get("url")
    if not isinstance(raw,str) or len(raw)>1000:
        return None
    try:
        u=urlsplit(raw)
    except ValueError:
        return None
    try:
        approved = (u.scheme=="https" and u.hostname in {"reddit.com","www.reddit.com"}
                    and not u.username and not u.password and u.port in (None,443))
    except ValueError:
        approved = False
    if not approved:
        return None
    pieces=u.path.strip("/").split("/")
    if len(pieces)<4 or pieces[0].lower()!="r" or pieces[2].lower()!="comments":
        return None
    # A source belongs to the exact observed subreddit AND catalog niche,
    # not to a similarly named community or a guessed market.
    suburb=pieces[1].lower()
    matches=[
        s.source_id for s in atlas.values()
        if s.reddit_subreddit.lower()==suburb
        and s.niche == obs.get("niche")
    ]
    return matches[0] if len(matches)==1 else None


def _valid_example(raw: Mapping[str, Any]) -> tuple[str,str,str]:
    if set(raw)!={
        "example_ref", "lesson_key", "niche", "approval_class",
        "human_approved", "reuse_permission", "contains_personal_data",
        "original_commercial_outcome_verified", "text_retained",
        "evidence_content_sha256",
    }:
        raise ValueError("approved example schema mismatch")
    example = raw["example_ref"]
    lesson = raw["lesson_key"]
    niche = raw["niche"]
    if (not isinstance(example,str) or not SAFE_ID.fullmatch(example)
            or not isinstance(lesson,str) or lesson not in EXAMPLE_LESSONS
            or not isinstance(niche,str) or not SAFE_ID.fullmatch(niche)
            or raw["approval_class"] not in ("SYNTHETIC_SCENARIO", "PERMISSIONED_DEIDENTIFIED_EXAMPLE")
            or raw["human_approved"] is not True
            or raw["reuse_permission"] != "INTERNAL_RETRIEVAL_ONLY"
            or raw["contains_personal_data"] is not False
            or raw["original_commercial_outcome_verified"] is not False
            or raw["text_retained"] is not False
            or not isinstance(raw["evidence_content_sha256"],str)
            or not HEX.fullmatch(raw["evidence_content_sha256"])):
        raise ValueError("untrusted example, outcome or rights")
    return example,lesson,niche


def build_market_knowledge_graph(
    repo_root: Path, *, as_of: datetime,
    approved_examples: list[Mapping[str,Any]] | None = None,
) -> dict[str,Any]:
    if not isinstance(as_of,datetime) or as_of.utcoffset() is None:
        raise ValueError("aware graph timestamp required")
    now=as_of.astimezone(timezone.utc)
    examples=approved_examples or []
    if not isinstance(examples,list) or len(examples)>MAX_EXAMPLES:
        raise ValueError("bounded example set required")
    atlas={s.source_id:s for s in SOURCES}
    nodes:dict[str,dict[str,Any]]={}
    edges:dict[str,dict[str,Any]]={}
    quarantined=Counter()
    def node(kind:str,key:str, *, metadata:dict[str,Any] | None=None)->str:
        ident=f"{kind}:{key}"
        row={"node_id":ident,"node_type":kind,"metadata":metadata or {}}
        if ident in nodes and nodes[ident]!=row:
            raise ValueError("conflicting graph node")
        nodes[ident]=row
        return ident
    def edge(source:str,relation:str,target:str, *, provenance:str, observed_at:str | None=None)->None:
        if source not in nodes or target not in nodes:
            raise ValueError("dangling graph edge")
        ref=_hash(source,relation,target,provenance)
        value={
            "edge_id":"edge_"+ref[:24], "source":source,
            "relation":relation, "target":target,
            "provenance_sha256":provenance,
            "observed_at":observed_at,
            "claim_status":"CATEGORICAL_SOURCE_RELATION_NOT_BUYER_PROOF",
        }
        if ref in edges and edges[ref]!=value:
            raise ValueError("conflicting graph relationship")
        edges[ref]=value
    # Reuse existing source registry, source scopes and product catalogue.
    for item in SOURCES:
        sid=node("research_source",item.source_id,metadata={
            "access_class":item.access,
            "automation_state":item.automation_state,
            "source_rights":"INDEXED_REFERENCE_ONLY_NOT_CONTENT_REUSE",
            "independently_verified_buyer":False,
        })
        if item.niche:
            nid=node("market_vertical",item.niche)
            edge(sid,"RESEARCH_SOURCE_COVERS_VERTICAL",nid,provenance=_hash("atlas",item.source_id))
        if item.geography:
            gid=node("geographic_scope",item.geography.lower())
            edge(sid,"RESEARCH_SOURCE_DECLARES_SCOPE",gid,provenance=_hash("atlas",item.source_id))
        offer=node("offer_hypothesis",item.offer_key)
        edge(sid,"SOURCE_RESEARCHES_OFFER",offer,provenance=_hash("atlas",item.source_id))
    for product in DATA_PRODUCTS:
        node("empire_data_product",product.key,metadata={
            "evidence_gate":"PRODUCT_CLAIM_REQUIRES_SOURCE_RECEIPT",
            "commercial_activation_verified":False,
        })
    for topic,mapping in SOLUTION_MAP.items():
        tid=node("problem_theme",topic)
        offer=node("offer_hypothesis",mapping["offer_key"])
        edge(tid,"MAY_INFORM_OFFER_HYPOTHESIS",offer,provenance=_hash("solution_map",topic))
        for p in mapping["products"]:
            if p in {entry.key for entry in DATA_PRODUCTS}:
                pid=node("empire_data_product",p,metadata={
                    "evidence_gate":"PRODUCT_CLAIM_REQUIRES_SOURCE_RECEIPT",
                    "commercial_activation_verified":False,
                })
                edge(tid,"MAY_INFORM_DATA_PRODUCT",pid,provenance=_hash("solution_map",topic,p))

    learning=_read(repo_root,"runtime/community_intent/source_learning_latest.json",MAX_BYTES)
    learning_state="UNAVAILABLE"
    learning_count=0
    unmapped_learning_count=0
    if learning:
        try:
            stamp=_time(learning["generated_at"])
            if (learning.get("schema_version")!=LEARNING_SCHEMA
                    or learning.get("mode")!="OBSERVE"
                    or learning.get("execution_authority")!="NONE"
                    or learning.get("actual_revenue_learning")!="REQUIRES_VERIFIED_CORTEX_AND_ECONOMIC_MEMORY"
                    or not isinstance(learning.get("source_results"),list)
                    or not 0<=len(learning["source_results"])<=len(SOURCES)
                    or stamp>now or now-stamp>LEARNING_AGE):
                learning_state="HELD_UNTRUSTED_OR_STALE"
            else:
                expected={
                    source_id((s.reddit_subreddit,s.reddit_query,s.niche,s.geography)):s.source_id
                    for s in SOURCES if s.reddit_subreddit
                }
                seen=set()
                matched=[]
                for row in learning["source_results"]:
                    if not isinstance(row,dict) or set(row)!={
                        "attempted_cycles","explicit_requests_unverified",
                        "new_posts","operator_problems_unverified",
                        "seller_pitches","source_id","successful_retrievals"
                    }:
                        raise ValueError("untrusted source learning shape")
                    ident=row["source_id"]
                    if not isinstance(ident,str) or len(ident)>200 or ident in seen:
                        raise ValueError("invalid or duplicate source learning identity")
                    seen.add(ident)
                    if any(type(row[f]) is not int or not 0 <= row[f] <= 10000
                           for f in ("attempted_cycles","explicit_requests_unverified",
                                     "new_posts","operator_problems_unverified",
                                     "seller_pitches","successful_retrievals")):
                        raise ValueError("untrusted source learning counts")
                    if row["successful_retrievals"]>row["attempted_cycles"]:
                        raise ValueError("invalid source learning retrievals")
                    # Validate ALL source rows before accepting ANY diagnostics.
                    if ident in expected:
                        matched.append((expected[ident],row))
                    else:
                        unmapped_learning_count+=1
                report_fingerprint=_hash("community_learning_report",stamp.isoformat(),LEARNING_SCHEMA)
                report_node=node("research_analytics_report",report_fingerprint[:24],metadata={
                    "report_type":"PUBLIC_SOURCE_RETRIEVAL_DIAGNOSTICS",
                    "observed_at":stamp.isoformat(),
                    "counts_are_buyer_demand":False,
                    "customer_outcomes_authenticated":False,
                    "underlying_content_reused":False,
                })
                for source_key,row in matched:
                    node_id=f"research_source:{source_key}"
                    nodes[node_id]["metadata"]["retrieval_cycles_observed"]=row["attempted_cycles"]
                    nodes[node_id]["metadata"]["public_posts_observed"]=row["new_posts"]
                    edge(report_node,"REPORTS_ON_RETRIEVAL_HEALTH",node_id,
                         provenance=_hash("source_diagnostic",report_fingerprint,source_key),
                         observed_at=stamp.isoformat())
                learning_count=len(matched)
                learning_state=("PARTIAL_SOURCE_DIAGNOSTICS_UNMAPPED_SOURCE_IDS"
                                if unmapped_learning_count else "READ_ONLY_SOURCE_DIAGNOSTICS")
        except (KeyError,TypeError,ValueError):
            learning_count=0
            unmapped_learning_count=0
            learning_state="HELD_UNTRUSTED_OR_STALE"

    observations=_read(repo_root,"runtime/community_intent/observations.json",MAX_BYTES)
    observed_state="UNAVAILABLE"
    observed_count=0
    if observations:
        try:
            updated=_time(observations["updated_at"])
            records=observations["observations"]
            if (observations.get("schema_version")!="empire.community_intent_history.v1"
                    or not isinstance(records,list) or len(records)>MAX_OBSERVATIONS
                    or updated>now or now-updated>OBS_AGE):
                observed_state="HELD_UNTRUSTED_OR_STALE"
            else:
                seen_posts=set()
                for obs in records:
                    if not isinstance(obs,dict):
                        quarantined["MALFORMED_PUBLIC_OBSERVATION"]+=1
                        continue
                    sid=_source_for_observation(obs,atlas)
                    try:
                        timestamp=_time(obs["observed_at"])
                        if timestamp>now or now-timestamp>OBS_AGE:
                            raise ValueError("out of window")
                        pain=obs["pain_points"]
                        if not isinstance(pain,list) or not 1<=len(pain)<=8 or any(
                            p not in SOLUTION_MAP for p in pain
                        ):
                            raise ValueError("unknown topic")
                        raw=obs["url"]
                        post_id=_hash(raw)
                        if post_id in seen_posts:
                            raise ValueError("duplicate post")
                        if sid is None:
                            raise ValueError("unknown or unlicensed research source")
                    except (ValueError,KeyError,TypeError):
                        quarantined["UNATTRIBUTED_OR_INVALID_POST"]+=1
                        continue
                    seen_posts.add(post_id)
                    marker=node("public_observation",post_id[:24],metadata={
                        "source_ref_sha256":post_id,
                        "quote_or_author_retained":False,
                        "reusable_for_training":False,
                        "source_license_verified":False,
                        "confidence_for_buyer_conversion":None,
                    })
                    edge(marker,"CITED_FROM_PUBLIC_SOURCE",f"research_source:{sid}",
                         provenance=_hash("community_observation",post_id),observed_at=timestamp.isoformat())
                    for topic in sorted(set(pain)):
                        edge(marker,"UNVERIFIED_TOPIC_TAG",f"problem_theme:{topic}",
                             provenance=_hash("classifier",post_id,topic),observed_at=timestamp.isoformat())
                    observed_count+=1
                observed_state="PUBLIC_RESEARCH_INDEXED_WITH_HELD_CONTENT"
        except (ValueError,KeyError,TypeError):
            observed_state="HELD_UNTRUSTED_OR_STALE"

    example_count=0
    seen_examples=set()
    for example in examples:
        if not isinstance(example,Mapping):
            raise ValueError("untrusted approved example")
        ref,lesson,niche=_valid_example(example)
        fingerprint=(ref,lesson,niche,example["evidence_content_sha256"],example["approval_class"])
        if fingerprint in seen_examples:
            continue
        seen_examples.add(fingerprint)
        ident=node("approved_example",ref,metadata={
            "approval_class":example["approval_class"],
            "lesson_key":lesson,
            "source_content_sha256":example["evidence_content_sha256"],
            "raw_transcript_retained":False,
            "buyer_commercial_outcome_verified":False,
            "model_weight_training_authorized":False,
        })
        vertical=node("market_vertical",niche)
        edge(ident,"EXAMPLE_TEACHES_MARKET",vertical,provenance=_hash("approved_example",ref))
        edge(ident,"EXAMPLE_ILLUSTRATES_THEME",f"problem_theme:{LESSON_TOPIC[lesson]}",
             provenance=example["evidence_content_sha256"])
        example_count+=1
    # Fully typed graph: edges never represent a public observation as a
    # buyer, authenticated conversion, procurement mandate or payment.
    return {
        "schema_version":SCHEMA, "mode":"OBSERVE",
        "status":"PARTIAL_MARKET_GRAPH_FROM_EXISTING_SOURCES",
        "built_at":now.isoformat(),
        "node_count":len(nodes),"edge_count":len(edges),
        "research_sources":len(SOURCES),
        "intelligence_data_products":len(DATA_PRODUCTS),
        "public_observations_indexed":observed_count,
        "approved_scenario_lessons":example_count,
        "unattributed_or_invalid_observations":sum(quarantined.values()),
        "public_research_health":observed_state,
        "community_learning_health":learning_state,
        "community_source_diagnostic_rows":learning_count,
        "unmapped_source_diagnostic_rows":unmapped_learning_count,
        "nodes":list(sorted(nodes.values(),key=lambda n:n["node_id"])),
        "edges":list(sorted(edges.values(),key=lambda e:e["edge_id"])),
        "market_truth_provenance_verified":False,
        "buyer_conversation_verified":False,
        "customer_roi_verified":False,
        "model_weights_updated":False,
        "community_text_reused_for_training":False,
        "external_crawler_run":False,
        "customer_data_accessed":False,
        "outbound_authorized":False,
        "payment_authorized":False,
        "execution_authority":"none",
    }


def prepare_market_conversation_brief(
    graph: Mapping[str,Any], *, niche: str,
) -> dict[str,Any]:
    if (graph.get("schema_version")!=SCHEMA or graph.get("execution_authority")!="none"
            or graph.get("model_weights_updated") is not False
            or graph.get("buyer_conversation_verified") is not False
            or not isinstance(niche,str) or not SAFE_ID.fullmatch(niche)):
        raise ValueError("untrusted graph or market scope")
    target=f"market_vertical:{niche}"
    if target not in {n["node_id"] for n in graph["nodes"]}:
        return {"status":"MARKET_NOT_INDEXED","niche":niche,
                "topics":[],"lessons":[],"buyer_proof":False}
    source_ids={
        e["source"] for e in graph["edges"]
        if e["relation"]=="RESEARCH_SOURCE_COVERS_VERTICAL" and e["target"]==target
    }
    posts={
        e["source"] for e in graph["edges"]
        if e["relation"]=="CITED_FROM_PUBLIC_SOURCE" and e["target"] in source_ids
    }
    topic_counts=Counter(
        e["target"].split(":",1)[1] for e in graph["edges"]
        if e["relation"]=="UNVERIFIED_TOPIC_TAG" and e["source"] in posts
    )
    # Reviewed templates avoid republishing a scraped author's wording.
    questions={
        "lead_generation": "Which lead channels deliver qualified enquiries, and how is quality measured?",
        "sales_conversion": "Where do enquiries drop out before an accepted commercial offer?",
        "search_visibility": "Which organic search markets and services matter to your customers?",
        "automation_ops": "Which manual workflow is losing the most response time?",
        "data_intelligence": "Which original data source or missing field blocks a decision?",
        "revenue_growth": "Which margin and fulfilment metrics would prove the result?",
        "storm_demand": "What area-level evidence shows exposure without assuming damage?",
    }
    lessons=sorted({
        n["metadata"]["lesson_key"]
        for n in graph["nodes"]
        if n["node_type"]=="approved_example"
        and any(e["source"]==n["node_id"] and e["target"]==target
                for e in graph["edges"])
    })
    return {
        "status":"PUBLIC_RESEARCH_BRIEF_NOT_COMMERCIAL_VERIFICATION",
        "niche":niche,
        "source_count":len(source_ids),
        "public_observation_count":len(posts),
        "topics":[{
            "problem_theme":topic,"distinct_public_observation_count":count,
            "truth_level":"UNVERIFIED_COMMUNITY_CLASSIFICATION",
            "next_human_question":questions[topic],
            "existing_source_research_next_action":SOLUTION_MAP[topic]["next_actions"][0],
        } for topic,count in sorted(topic_counts.items(),key=lambda x:(-x[1],x[0]))[:5]],
        "lessons":lessons,
        "buyer_proof":False,
        "realized_revenue_proof":False,
        "no_training_on_private_chats":True,
        "execution_authority":"none",
    }
