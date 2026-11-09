"""Optional, NOT LIVE: existing private CRM + original V4.11 held-source review.

This is an additive entrypoint inside the SAME 8783 CRM process, to be used
only after original owner approves a bounded systemd LoadCredential and CRM
restart. Never copies private DB password into git, browser, config or logs.
"""
from __future__ import annotations

import os
from pathlib import Path
from psycopg.conninfo import conninfo_to_dict

from data_cloud_verify_ui_entrypoint_20261108 import app
from data_cloud_private_entrypoint_20261107 import crm_verifier, authority
from empire_os.predictive_cloud_v410_rights_reader import EmpireDbHeldSourceRightsReader
from private_crm_original_v411_source_review_candidate_20261108 import (
    attach_private_source_review,
)

CRED_NAME = "empire-predictive-source-rights-dsn"
DIRECTORY = "/run/credentials/empire-revenue-crm-pilot.service"

directory = os.environ.get("CREDENTIALS_DIRECTORY", "")
if directory != DIRECTORY:
    raise RuntimeError("original_private_crm_systemd_credentials_required")
secret = Path(DIRECTORY) / CRED_NAME
if (secret.is_symlink() or not secret.is_file()
    or secret.stat().st_size > 1024):
    raise RuntimeError("original_private_source_rights_credential_missing")
dsn = secret.read_text().strip()
parameters = conninfo_to_dict(dsn)
if (parameters.get("host") != "127.0.0.1"
    or parameters.get("port") != "5432"
    or parameters.get("dbname") != "empiredb"
    or parameters.get("user") != "empire_predictive_rights_login"
    or not parameters.get("password")):
    raise RuntimeError("original_restricted_rights_dsn_contract_changed")

reader = EmpireDbHeldSourceRightsReader(dsn)
del dsn, parameters
attach_private_source_review(app, crm_verifier, authority, reader)
