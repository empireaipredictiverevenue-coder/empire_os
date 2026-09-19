"""Explainable commercial scoring, pricing and forecasting for Empire OS."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import exp
from typing import Any, Mapping

DIMENSIONS = ("buying_intent", "urgency", "budget_capacity", "conversion_probability", "contactability", "competitive_pressure", "lifetime_value", "lead_purchase_propensity")
WEIGHTS = {"buying_intent": .20, "urgency": .12, "budget_capacity": .12, "conversion_probability": .18, "contactability": .10, "competitive_pressure": .08, "lifetime_value": .10, "lead_purchase_propensity": .10}

def _num(v: Any, default=0.0):
    try: return float(v)
    except (TypeError, ValueError): return default

def _clamp(v, lo=0., hi=100.): return round(max(lo, min(hi, v)), 2)

def _truthy(v): return v is True or str(v).strip().lower() in {"1","true","yes","y","on"}

def _text(r: Mapping[str, Any]):
    fields=("signals","signal","intent_signal","buying_signal","notes","description","details","activity","recent_event")
    return " ".join(str(r.get(k,"")) for k in fields).lower()

def score_buying_intent(r):
    x=_num(r.get("intent_score"),-1)
    if x>=0:return _clamp(x)
    t=_text(r); s=8
    for k,p in (("buy",30),("buying",30),("intent",25),("quote",22),("rfq",28),("hiring",12),("expansion",15),("new location",18),("new service",12),("funding",10),("acquisition",12),("urgent",25),("emergency",30)):
        if k in t:s+=p
    if _truthy(r.get("replied")):s+=22
    if _truthy(r.get("previous_purchase")):s+=25
    s+=min(_num(r.get("engagement_events"))*2.5,15)
    return _clamp(s)

def score_urgency(r):
    x=_num(r.get("urgency_score"),-1)
    if x>=0:return _clamp(x)
    t=_text(r);s=18
    for k,p in (("urgent",45),("emergency",50),("asap",40),("immediately",40),("deadline",25),("this week",25)):
        if k in t:s+=p
    return _clamp(s+10 if _truthy(r.get("recent_event")) else s)

def score_budget_capacity(r):
    x=_num(r.get("budget_score"),-1)
    if x>=0:return _clamp(x)
    rev=_num(r.get("annual_revenue")); emp=_num(r.get("employees")); s=25
    for threshold,points in ((10_000_000,55),(2_000_000,40),(500_000,28),(100_000,15)):
        if rev>=threshold:s+=points;break
    s += 20 if emp>=100 else 12 if emp>=20 else 6 if emp>=5 else 0
    if _truthy(r.get("funding")) or _truthy(r.get("expansion")):s+=12
    return _clamp(s)

def score_conversion_probability(r):
    x=_num(r.get("conversion_probability"),-1)
    if x>=0:return _clamp(x*100 if x<=1 else x)
    s=20+(30 if _truthy(r.get("replied")) else 0)+(15 if _truthy(r.get("engaged")) else 0)+(25 if _truthy(r.get("previous_purchase")) else 0)
    s+=min(_num(r.get("lead_score"))*0.15,15)+min(_num(r.get("omega_score"))*0.02,10)
    return _clamp(s)

def score_contactability(r):
    x=_num(r.get("contactability_score"),-1)
    if x>=0:return _clamp(x)
    s=(35 if r.get("email") else 0)+(30 if r.get("phone") else 0)+(15 if r.get("website") else 0)+(10 if r.get("contact_name") else 0)+(10 if _truthy(r.get("email_verified")) else 0)
    return _clamp(s)

def score_competitive_pressure(r):
    x=_num(r.get("competitive_pressure"),-1)
    if x>=0:return _clamp(x)
    available=_num(r.get("available_leads")); buyers=_num(r.get("active_buyers"))
    return 50 if available<=0 else _clamp(25+buyers/max(available,1)*150)

def score_lifetime_value(r):
    x=_num(r.get("ltv_score"),-1)
    if x>=0:return _clamp(x)
    ltv=_num(r.get("expected_ltv")) or _num(r.get("expected_monthly_spend"))*max(_num(r.get("expected_months"),6),1)
    return 100 if ltv>=25000 else 85 if ltv>=10000 else 70 if ltv>=5000 else 50 if ltv>=1000 else 30 if ltv>0 else 20

def score_lead_purchase_propensity(r):
    x=_num(r.get("lead_purchase_propensity"),-1)
    if x>=0:return _clamp(x*100 if x<=1 else x)
    s=15+(20 if r.get("niche") else 0)+(35 if _truthy(r.get("uses_lead_gen")) else 0)+(15 if _truthy(r.get("uses_agency")) else 0)+(25 if _num(r.get("historical_leads_bought"))>0 else 0)+(20 if _num(r.get("lead_budget_monthly"))>0 else 0)
    return _clamp(s)

@dataclass(frozen=True)
class RevenueIntelligence:
    buying_intent:float; urgency:float; budget_capacity:float; conversion_probability:float; contactability:float; competitive_pressure:float; lifetime_value:float; lead_purchase_propensity:float
    opportunity_score:float; probability_of_purchase:float; expected_monthly_value:float; expected_ltv:float; recommended_price:float; confidence:float; tier:str; reasons:tuple[str,...]
    def as_dict(self):
        d=asdict(self);d["reasons"]=list(self.reasons);return d

def analyze(record: Mapping[str,Any], *, base_lead_value:float=25.) -> RevenueIntelligence:
    values={k:f(record) for k,f in {"buying_intent":score_buying_intent,"urgency":score_urgency,"budget_capacity":score_budget_capacity,"conversion_probability":score_conversion_probability,"contactability":score_contactability,"competitive_pressure":score_competitive_pressure,"lifetime_value":score_lifetime_value,"lead_purchase_propensity":score_lead_purchase_propensity}.items()}
    opp=_clamp(sum(values[k]*WEIGHTS[k] for k in DIMENSIONS)); prior=max(.005,min(.5,_num(record.get("purchase_prior"),.05)))
    p=round(max(.005,min(.95,.65*(1/(1+exp(-(opp-60)/11)))+.35*prior)),4)
    spend=_num(record.get("expected_monthly_spend")) or base_lead_value*max(_num(record.get("expected_monthly_lead_volume"),1),1)
    monthly=round(spend*p,2);months=max(_num(record.get("expected_months"),6),1);ltv=round(monthly*months,2)
    price=round(max(1,base_lead_value*min((.55+opp/100)*(.85+.30*p),2.25)),2)
    filled=sum(bool(record.get(k)) for k in ("email","phone","website","contact_name","niche"));confidence=_clamp(35+filled*10+(10 if "lead_score" in record else 0)+(10 if "enrichment_score" in record else 0))
    tier="prime" if opp>=80 else "hot" if opp>=65 else "warm" if opp>=45 else "cold" if opp>=25 else "inactive"
    reasons=tuple(x for v,x in sorted(((values[k],x) for k,x in (("buying_intent","strong buying intent"),("urgency","time-sensitive demand"),("budget_capacity","healthy budget capacity"),("conversion_probability","high conversion likelihood"),("contactability","easy to contact"),("competitive_pressure","scarce/competitive inventory"),("lifetime_value","high lifetime value potential"),("lead_purchase_propensity","likely to purchase lead inventory"))),reverse=True) if v>=65)[:4] or ("limited commercial signals; continue enrichment",)
    return RevenueIntelligence(**values,opportunity_score=opp,probability_of_purchase=p,expected_monthly_value=monthly,expected_ltv=ltv,recommended_price=price,confidence=confidence,tier=tier,reasons=reasons)

def analyze_many(records, *, base_lead_value=25.):
    return sorted((analyze(r,base_lead_value=base_lead_value).as_dict() for r in records),key=lambda x:(x["expected_monthly_value"],x["opportunity_score"]),reverse=True)

def forecast(records, *, base_lead_value=25.):
    rows=analyze_many(records,base_lead_value=base_lead_value);monthly=round(sum(x["expected_monthly_value"] for x in rows),2)
    return {"records":len(rows),"prime":sum(x["tier"]=="prime" for x in rows),"hot":sum(x["tier"]=="hot" for x in rows),"warm":sum(x["tier"]=="warm" for x in rows),"expected_monthly_value":monthly,"forecast_30d":monthly,"forecast_90d":round(monthly*3,2),"forecast_365d":round(monthly*12,2),"weighted_probability":round(sum(x["probability_of_purchase"] for x in rows)/len(rows),4) if rows else 0.,"generated_at":datetime.now(timezone.utc).isoformat()}
