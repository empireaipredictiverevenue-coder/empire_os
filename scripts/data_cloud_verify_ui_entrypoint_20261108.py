"""One additive browser-only UI check on original protected CRM issuer.

Do not replace CRM login, session handling, frozen HTML/JS, or Data Cloud APIs.
"""
from data_cloud_private_entrypoint_20261107 import app
from data_cloud_verify_ui_patch_20261108 import build_verified_routes

build_verified_routes(app)
