#!/usr/bin/env python3
"""Research-only reuse of unverified first-party buyer observations."""
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from empire_os.lead_qualification_tiers import qualify
from empire_os.lead_intelligence_formula import score
from empire_os.scientific_lead_reasoning import reason

BASE=Path('/srv/empire_os/runtime/buyer_network_intelligence')

def build(base=BASE):
 observations=json.loads((base/'targeted_evidence_observations_latest.json').read_text())
 qualification=json.loads((base/'founder_qualification_actions_latest.json').read_text())
 if (observations.get('schema_version')!='empire.targeted_evidence_observations.v1'
     or observations.get('mode')!='OBSERVE' or observations.get('execution_authority')!='none'
     or observations.get('outbound_sent') is not False):
  raise ValueError('unsafe_observations')
 if (qualification.get('schema_version')!='empire.buyer_qualification_actions.v1'
     or qualification.get('mode')!='OBSERVE' or qualification.get('execution_authority')!='none'
     or qualification.get('outbound_enabled') is not False or qualification.get('outbound_sent') is not False):
  raise ValueError('unsafe_qualification_snapshot')
 targets={x['domain']:x for x in qualification['targets'] if x.get('founder_research_decision')=='CONTINUE_RESEARCH'}
 grouped={domain:[] for domain in targets}
 for item in observations['requirements']:
  domain=item['domain']
  if (domain not in targets or item.get('verified') is not False
      or item.get('outbound_authorized') is not False
      or item.get('commercial_terms_approved') is not False):
   raise ValueError('unsafe_observation_row')
  for lead in item.get('claim_leads',[]):
   if not isinstance(lead,dict) or lead.get('evidence_status')!='UNVERIFIED_CLAIM_LEAD':
    raise ValueError('unverified_claim_only')
   url=lead.get('url')
   if not isinstance(url,str):raise ValueError('invalid_research_source_url')
   parsed=urlsplit(url)
   if parsed.scheme!='https' or parsed.hostname not in (domain,'www.'+domain) or parsed.username or parsed.password:
    raise ValueError('non_first_party_research_url')
   grouped[domain].append({'requirement':item['requirement'],'source_url':url,
                           'phrase':lead['matched_phrase'],'evidence_status':'UNVERIFIED_CLAIM_LEAD'})
 rows=[]
 for domain,buyer in targets.items():
  decision = ('USE_FOR_RESEARCH' if grouped[domain] else 'INVESTIGATE_MISSING_EVIDENCE')
  gaps=len(buyer['missing_evidence'])
  opportunity_score=min(100,20+15*len(buyer['verticals'])+10*len(set(x['requirement'] for x in grouped[domain]))+5*len(grouped[domain]))
  qualification_score=max(0,100-25*gaps)
  # Research-only signals cannot establish buyer identity, consent, commercial terms, or decision-maker authority.
  # This is a public-claims RESEARCH consumer, not an authenticated proof
  # reader. Even apparent `verified_evidence` fields cannot promote tiers.
  tier_result=qualify(None)
  verified_qualification_tier=tier_result['qualification_tier']
  ranking_tier=('EXECUTIVE_RESEARCH' if opportunity_score>=85 else 'PREMIUM_RESEARCH' if opportunity_score>=65 else 'PRIORITY_RESEARCH' if opportunity_score>=45 else 'STANDARD_RESEARCH')
  formula=score(None,None)  # Only a canonical proof adapter may supply scoring inputs.
  observations=[{'source_id':signal['source_url'],'source_type':'public_first_party_claim',
                 'direction':'support'} for signal in grouped[domain]]
  scientific=reason(hypothesis='Company has relevant commercial buyer demand',observations=observations)
  rows.append({'domain':domain,'verticals':buyer['verticals'],
               'lead_intelligence_formula':formula,
               'scientific_reasoning':scientific,
               'opportunity_score':opportunity_score,'opportunity_rank_tier':ranking_tier,
               'evidence_completeness_indicator':qualification_score,
               'evidence_completeness_is_heuristic':True,
               'qualification_tier':verified_qualification_tier,
               'tier_upgrade_blockers':buyer['missing_evidence'],
               'next_tier':tier_result['next_tier'],
               'missing_verified_proofs':tier_result['missing_verified_proofs'],
               'score_is_verified_commercial_intent':False,
               'ai_routing_decision':decision,
               'decision_reason':('source_linked_claim_leads_available' if grouped[domain] else 'no_matching_claim_leads'),
               'commercial_activation_decision':'BLOCK',
               'research_signals':grouped[domain],
               'open_requirements':buyer['missing_evidence'],
               'permitted_uses':['opportunity_radar_research','buyer_intelligence_research','niche_matching_research'],
               'prohibited_uses':['outbound','buyer_admission','verified_payout_claim','commercial_offer','payment','fulfilment'],
               'authority':'RESEARCH_ONLY','qualified_buyer':False,'outbound_authorized':False})
 return {'schema_version':'empire.buyer_intelligence_reuse.v1','mode':'OBSERVE',
         'execution_authority':'none','buyer_count':len(rows),'buyers':rows,
         'outbound_sent':False,'commercial_terms_verified':False}

if __name__=='__main__':
 report=build()
 fd,tmp=tempfile.mkstemp(prefix='.intelligence_reuse_',dir=BASE)
 try:
  os.fchmod(fd,0o600)
  with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2);f.write('\n')
  target=BASE/'buyer_intelligence_reuse_latest.json'
  if target.is_symlink():raise ValueError('unsafe_target')
  os.replace(tmp,target)
 finally:
  if os.path.exists(tmp):os.unlink(tmp)
 print(json.dumps({'status':'PASS','buyer_count':report['buyer_count'],
                   'research_signal_count':sum(len(x['research_signals']) for x in report['buyers']),
                   'outbound_sent':False}))
