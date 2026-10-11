"""Evidence-gated lead tiers; opportunity scores never substitute for proof."""
from __future__ import annotations
from collections.abc import Mapping

TIERS=('BASIC','PRE_QUALIFIED','PREMIUM','EXECUTIVE')
PROOFS={
 'PRE_QUALIFIED':('company_identity_verified','icp_match_verified','demand_verified'),
 'PREMIUM':('company_identity_verified','icp_match_verified','demand_verified',
            'contact_path_verified','commercial_terms_verified','compliance_verified'),
 'EXECUTIVE':('company_identity_verified','icp_match_verified','demand_verified',
              'contact_path_verified','commercial_terms_verified','compliance_verified',
              'decision_maker_verified','strategic_value_verified'),
}

def qualify(evidence:Mapping[str,object]|None)->dict:
 """Only explicit boolean True counts as independently verified evidence."""
 evidence=evidence if isinstance(evidence,Mapping) else {}
 tier='BASIC'
 for candidate in TIERS[1:]:
  if all(evidence.get(key) is True for key in PROOFS[candidate]):
   tier=candidate
  else:
   break
 next_tier=TIERS[min(TIERS.index(tier)+1,len(TIERS)-1)]
 missing=[key for key in PROOFS.get(next_tier,()) if evidence.get(key) is not True]
 return {'qualification_tier':tier,'next_tier':next_tier if tier!='EXECUTIVE' else None,
         'missing_verified_proofs':missing,'commercial_activation_authorized':False}
