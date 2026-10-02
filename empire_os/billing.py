"""Retired legacy billing compatibility surface.

EmpireOS commercial settlement is USDT on BSC only. New payment requests,
verification, fulfilment and revenue truth must use the canonical governed
payment path.
"""
from __future__ import annotations
from empire_os.payment_rail_policy import RetiredPaymentRailError, canonical_payment_rail

def status() -> dict:
    out = canonical_payment_rail()
    out.update({"status":"RETIRED","component":"legacy_billing","execution_allowed":False})
    return out

def _retired(*_args, **_kwargs):
    raise RetiredPaymentRailError("legacy billing retired; use governed USDT/BSC payment flow")

paypal_create_subscription = _retired
paypal_get_subscription = _retired
paypal_cancel_subscription = _retired
crypto_payment_request = _retired
verify_crypto_payment = _retired

class BillingEngine:
    def available_methods(self): return [{"method":"usdt_bsc","chain_id":56}]
    def start_subscription(self,*args,**kwargs): return _retired(*args,**kwargs)
