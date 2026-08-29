"""Audit 4.2 — Data Classification levels (shared by masking/encryption)."""
from enum import Enum


class Classification(Enum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    RESTRICTED = 3


# Retention policy (Audit 4.3)
RETENTION_DAYS = {
    "leads": 730,
    "audit_logs": 2555,        # 7 years
    "email_copies": 90,
    "failed_logins": 30,
    "backup_files": 365,
}
