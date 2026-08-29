"""
Empire Omega OS — Security Audit Specification
=============================================
Data model of the Security Architecture Audit (CONFIDENTIAL v1.0).
Drives the audit_generator. External numbers are MOCKED config (no live
AWS/Splunk/AbuseIPDB). BSC USDT settlement is the real pay path.
"""
from dataclasses import dataclass, field
from typing import List

# ── MOCKED external baselines (doc "Current State" claims) ──
CURRENT_STATE = {
    "zero_trust": False,
    "oauth2": False,
    "jwt": False,
    "device_verification": False,
    "continuous_auth": False,
    "micro_segmentation": False,
    "tls_1_3": True,
    "aes256_db": False,
    "field_encryption": False,
    "encrypted_backups": False,
    "key_rotation": False,
    "waf_modsecurity": False,
    "rate_limiting": False,
    "ddos_protection": False,
    "ip_reputation": False,
    "traffic_anomaly": False,
    "gdpr_framework": True,
    "audit_logging": True,
    "pii_masking": False,
    "data_classification": False,
    "auto_deletion": False,
    "solana_rpc": False,
    "bsc_usdt": True,            # REAL pay path
    "tx_verification": True,     # REAL (bsc_settlement)
    "program_audit": False,
    "exploit_prevention": False,
    "tx_rate_limiting": False,
    "elk_stack": False,
    "prometheus": False,
    "siem": False,
    "threat_hunting": False,
    "incident_response": False,
}

# ── Audit findings (doc sections) ──
FINDINGS = [
    {"id": "A1", "area": "Zero-Trust", "severity": "CRITICAL",
     "gap": "No zero-trust architecture", "status": "OPEN"},
    {"id": "A2", "area": "Encryption", "severity": "CRITICAL",
     "gap": "Insufficient encryption at rest", "status": "OPEN"},
    {"id": "A3", "area": "Rate Limiting", "severity": "HIGH",
     "gap": "Missing rate limiting on sensitive endpoints", "status": "PARTIAL"},
    {"id": "A4", "area": "Blockchain", "severity": "HIGH",
     "gap": "No BSC USDT transaction verification hardening", "status": "PARTIAL"},
    {"id": "A5", "area": "Audit Logging", "severity": "HIGH",
     "gap": "Inadequate audit logging / PII in logs", "status": "OPEN"},
    {"id": "A6", "area": "Secrets", "severity": "MEDIUM",
     "gap": "Missing secrets rotation / log-leak hygiene", "status": "OPEN"},
    {"id": "A7", "area": "Anomaly", "severity": "MEDIUM",
     "gap": "No anomaly / threat detection", "status": "OPEN"},
]

# ── Hardening controls implemented (mapped to modules) ──
CONTROLS = [
    {"id": "C1", "audit": "4.1", "name": "PII Masking",
     "module": "empire_os.security.pii_masking", "status": "IMPLEMENTED"},
    {"id": "C2", "audit": "2.1", "name": "Field-Level AES-256-GCM Encryption",
     "module": "empire_os.security.field_encryption", "status": "IMPLEMENTED"},
    {"id": "C3", "audit": "3.1", "name": "Rate Limiting (token bucket)",
     "module": "empire_os.security.rate_limiter", "status": "IMPLEMENTED"},
    {"id": "C4", "audit": "5 (BSC)", "name": "BSC USDT Settlement Verification",
     "module": "empire_os.security.bsc_settlement", "status": "IMPLEMENTED"},
    {"id": "C5", "audit": "6/Secrets", "name": "Secrets Hygiene & Log-Leak Scan",
     "module": "empire_os.security.secrets_hygiene", "status": "IMPLEMENTED"},
    {"id": "C6", "audit": "6.1-6.3", "name": "Security Monitor / SIEM / IR",
     "module": "empire_os.security.security_monitor", "status": "IMPLEMENTED"},
    {"id": "C7", "audit": "4.2", "name": "Data Classification",
     "module": "empire_os.security.data_classification", "status": "IMPLEMENTED"},
    # MOCKED / roadmap-only (no backing infra)
    {"id": "C8", "audit": "1.1", "name": "Zero-Trust / mTLS / Istio",
     "module": "MOCKED", "status": "ROADMAP"},
    {"id": "C9", "audit": "3.2", "name": "IP Reputation (AbuseIPDB)",
     "module": "MOCKED", "status": "ROADMAP"},
    {"id": "C10", "audit": "6.1", "name": "SIEM (Splunk/Elastic)",
     "module": "MOCKED", "status": "ROADMAP"},
    {"id": "C11", "audit": "2.2", "name": "Key Rotation (AWS KMS/Vault)",
     "module": "MOCKED", "status": "ROADMAP"},
]

# ── Implementation roadmap (doc Phase 1-4) ──
ROADMAP = {
    "Phase 1 CRITICAL (Wk1-2)": ["zero-trust", "field-encryption",
                                  "ddos-protection", "siem", "incident-response"],
    "Phase 2 HIGH (Wk3-4)": ["device-verification", "key-rotation",
                              "ip-reputation", "threat-hunting", "pii-masking"],
    "Phase 3 MEDIUM (Wk5-6)": ["continuous-auth", "encrypted-backups",
                                "traffic-anomaly", "data-retention", "chaos"],
    "Phase 4 OPT (Wk7-8)": ["perf", "reliability", "scalability",
                             "third-party-audit", "soc2"],
}

# ── Risk matrix (doc) ──
RISK_MATRIX = [
    ("Data breach", "CRITICAL", "Medium", "Encryption, access control, monitoring"),
    ("DDoS attack", "HIGH", "High", "WAF, rate limiting, DDoS service"),
    ("Insider threat", "HIGH", "Low", "MFA, audit logging, least privilege"),
    ("Ransomware", "CRITICAL", "Medium", "Backups, isolation, incident response"),
    ("BSC exploit", "HIGH", "Low", "Settlement verification, tx verification"),
    ("Service outage", "HIGH", "Medium", "HA architecture, chaos testing"),
]

# ── Compliance targets (doc) ──
COMPLIANCE = ["SOC 2 Type II", "ISO 27001", "GDPR", "CCPA", "PCI-DSS L1", "HIPAA-ready"]

# ── BSC settlement verification checklist (doc 5.2 ported) ──
BSC_VERIFY_CHECKLIST = [
    "recipient == vault 0x1339b487046B0ad924a10c20b1791608EA8595a8",
    "amount >= dust ($0.01)",
    "confirmations >= 15 (BSC finality)",
    "memo carries LEAD_ nonce (replay protection)",
    "per-wallet rate limit (100/hr)",
]

TARGET_VAULT = "0x1339b487046B0ad924a10c20b1791608EA8595a8"
