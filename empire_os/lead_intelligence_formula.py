"""Evidence-bounded scoring for research; never grants commercial authority."""
from __future__ import annotations
from collections.abc import Mapping
from math import isfinite

WEIGHTS={'icp_fit':0.25,'demand':0.25,'potential_value':0.20,
         'freshness':0.15,'transaction_readiness':0.15}
PROOF_WEIGHTS={'company_identity_verified':2,'icp_match_verified':1,
 'demand_verified':2,'contact_path_verified':2,'commercial_terms_verified':3,
 'compliance_verified':3,'decision_maker_verified':2,'strategic_value_verified':2}

def score(components:Mapping[str,object]|None, proofs:Mapping[str,object]|None)->dict:
 components=components if isinstance(components,Mapping) else {}
 proofs=proofs if isinstance(proofs,Mapping) else {}
 validated={}
 for key in WEIGHTS:
  value=components.get(key)
  if type(value) not in (int,float) or not isfinite(value) or not 0<=value<=100:
   validated[key]=None
  else:
   validated[key]=float(value)
 complete=all(value is not None for value in validated.values())
 opportunity=round(sum(validated[k]*w for k,w in WEIGHTS.items()),2) if complete else None
 confidence=round(100*sum(weight for key,weight in PROOF_WEIGHTS.items() if proofs.get(key) is True)/sum(PROOF_WEIGHTS.values()),2)
 return {'formula_version':'empire.lead_intelligence_formula.v2',
         'opportunity_score':opportunity,'evidence_confidence_score':confidence,
         'component_coverage':sum(value is not None for value in validated.values()),
         'component_count':len(WEIGHTS),'missing_components':[key for key,value in validated.items() if value is None],
         'score_is_verified_commercial_intent':False,'commercial_activation_authorized':False}
