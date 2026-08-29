"""
Empire Omega OS — Military-Grade Security Architecture
=======================================================
Implements the hardening roadmap from the Security Architecture Audit
(CONFIDENTIAL, v1.0). External third-party integrations (AWS KMS, Splunk
SIEM, AbuseIPDB, Cloudflare) are MOCKED with configurable constants so the
logic runs on the single-box incus deployment without external accounts.

Real, locally-executable logic:
  - PII masking in logs/reports
  - Field-level AES-256-GCM encryption (keys in Vault mock)
  - In-process rate limiting (token bucket per key)
  - BSC USDT settlement verification (vault 0x1339b487..., amount, recipient,
    finality, dust-filter, per-wallet rate limit)
  - Secrets hygiene scan (perms, plaintext-in-logs detection)

Chain: BSC USDT, vault 0x1339b487046B0ad924a10c20b1791608EA8595a8
"""
from empire_os.security.pii_masking import mask_log, mask_dict, DataClassifier
from empire_os.security.field_encryption import FieldEncryptor, encrypt_field, decrypt_field
from empire_os.security.rate_limiter import RateLimiter, RateLimitConfig
from empire_os.security.bsc_settlement import BSCSettlement, verify_settlement
from empire_os.security.secrets_hygiene import SecretsHygiene, scan_secrets
from empire_os.security.security_monitor import SecurityMonitor, record_event, SIEM

__all__ = [
    "mask_log", "mask_dict", "DataClassifier",
    "FieldEncryptor", "encrypt_field", "decrypt_field",
    "RateLimiter", "RateLimitConfig",
    "BSCSettlement", "verify_settlement",
    "SecretsHygiene", "scan_secrets",
    "SecurityMonitor", "record_event", "SIEM",
]
