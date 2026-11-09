"""Candidate only: preserve the entire existing protected startup chain."""
from private_crm_original_v411_source_entrypoint_20261108 import app
from data_cloud_private_entrypoint_20261107 import crm, crm_signer, bound
from empire_os.revenue_crm_signed_auth import build_signed_crm_tenant_authenticator
from empire_os.revenue_crm_api import build_authenticated_revenue_crm_resolver
from .mount import attach_search_evidence

# These are the already-validated original CRM key, active membership lookup
# and dedicated tenant connections. No new configuration or identity source.
authenticator = build_signed_crm_tenant_authenticator(
    {crm["key_id"]: crm_signer.public_key()}, load_membership=bound,
)
resolver = build_authenticated_revenue_crm_resolver(authenticator, crm["tenant_dsns"])
attach_search_evidence(app, resolver)
