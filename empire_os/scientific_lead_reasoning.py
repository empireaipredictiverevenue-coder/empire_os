"""Auditable evidence reasoning for research-only lead decisions."""
from __future__ import annotations
from collections.abc import Mapping
from math import isfinite, log, exp

SOURCE_WEIGHTS={'authenticated_commercial':1.0,'verified_first_party':0.85,
                'independent_corroboration':0.7,'public_first_party_claim':0.3,
                'unattributed':0.0}

def reason(*,hypothesis:str,observations:list[dict],prior:float|None=None)->dict:
 """Weights rank evidence; probabilities require empirically calibrated LRs."""
 if not isinstance(hypothesis,str) or not hypothesis.strip():raise ValueError('hypothesis_required')
 if not isinstance(observations,list):raise ValueError('observations_must_be_list')
 seen=set();accepted=[];rejected=[];weighted_support=0.0;weighted_contradiction=0.0
 for item in observations:
  if not isinstance(item,Mapping):raise ValueError('observation_must_be_mapping')
  source=item.get('source_type');identity=item.get('source_id');direction=item.get('direction')
  if source not in SOURCE_WEIGHTS or not isinstance(identity,str) or not identity.strip() or direction not in ('support','contradict'):
   rejected.append('invalid_evidence');continue
  if identity in seen:
   rejected.append('correlated_duplicate');continue
  seen.add(identity)
  weight=SOURCE_WEIGHTS[source]
  if direction=='support':weighted_support+=weight
  else:weighted_contradiction+=weight
  accepted.append({'source_id':identity,'source_type':source,'direction':direction,'weight':weight})
 posterior=None
 if prior is not None:
  if type(prior) not in (float,int) or not isfinite(prior) or not 0<prior<1:raise ValueError('invalid_prior')
  # Only empirical, independently calibrated likelihood ratios may update odds.
  ratios=[]
  for item in observations:
   ratio=item.get('calibrated_likelihood_ratio') if isinstance(item,Mapping) else None
   if ratio is not None:ratios.append(ratio)
  # Fail closed: no posterior until a separately validated calibration model exists.
  rejected.extend(['uncalibrated_likelihood_ratio']*len(ratios))
 return {'schema_version':'empire.scientific_lead_reasoning.v1','hypothesis':hypothesis,
         'weighted_support':round(weighted_support,3),'weighted_contradiction':round(weighted_contradiction,3),
         'observations':accepted,'rejection_reasons':rejected,'posterior_probability':posterior,
         'probability_calibrated':False,'research_priority_indicator':round(weighted_support-weighted_contradiction,3),
         'execution_authority':'none','commercial_activation_authorized':False}
