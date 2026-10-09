"""Documenso-only, OBSERVE-only signing gate for EmpireOS."""
from .policy import prepare_agreement
from .lifecycle import observe_webhook, verify_artifacts
__all__ = ["prepare_agreement", "observe_webhook", "verify_artifacts"]
