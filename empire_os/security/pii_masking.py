"""
Audit 4.1 — PII Masking
Mask emails, phones, wallet addresses, API keys in logs/reports/errors.
Unmask only via authorized call with audit trail.
"""
import re
from empire_os.security.data_classification import Classification, RETENTION_DAYS


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}")
# BSC / EVM address
ADDR_RE = re.compile(r"0x[a-fA-F0-9]{40}")
# BSC-style (legacy) — keep for compatibility but vault is BSC
SOL_RE = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
# API key-ish
KEY_RE = re.compile(r"(?i)(api[_-]?key|token|secret|privkey)[\"'\s:=]+[A-Za-z0-9_\-]{8,}")


def _mask_email(m):
    u, dom = m.group(0).split("@", 1)
    return u[:3] + "****@" + dom


def _mask_phone(m):
    d = re.sub(r"\D", "", m.group(0))
    if len(d) >= 10:
        return "+1 (***) ***-" + d[-4:]
    return "***-***-" + d[-4:] if len(d) >= 4 else "****"


def _mask_addr(m):
    a = m.group(0)
    return a[:4] + "..." + a[-4:]


def mask_log(text):
    """Mask all PII patterns in a string (logs, errors, reports)."""
    if not text:
        return text
    text = EMAIL_RE.sub(_mask_email, text)
    text = PHONE_RE.sub(_mask_phone, text)
    text = ADDR_RE.sub(_mask_addr, text)
    text = KEY_RE.sub(lambda m: m.group(0).split(m.group(1))[0] + m.group(1) + "=****", text)
    return text


def mask_dict(d, fields=None):
    """Recursively mask string values in a dict/structure for logging."""
    if isinstance(d, dict):
        return {k: mask_dict(v, fields) for k, v in d.items()}
    if isinstance(d, list):
        return [mask_dict(v, fields) for v in d]
    if isinstance(d, str):
        return mask_log(d)
    return d


# Data classification levels (Audit 4.2)
class DataClassifier:
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    RESTRICTED = "RESTRICTED"

    LEVELS = [PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED]

    @classmethod
    def classify(cls, field_name):
        f = (field_name or "").lower()
        if any(k in f for k in ("wallet", "privkey", "secret", "api_key", "password")):
            return cls.RESTRICTED
        if any(k in f for k in ("email", "phone", "revenue", "ssn", "card", "financial")):
            return cls.CONFIDENTIAL
        if any(k in f for k in ("score", "lead", "campaign", "niche")):
            return cls.INTERNAL
        return cls.PUBLIC


if __name__ == "__main__":
    sample = "User john@empire.ai paid 1240 to 0x1339b487046B0ad924a10c20b1791608EA8595a8 " \
             "phone +1 (305) 555-1234 api_key=abc123SECRET token=xyz789TOKEN"
    print(mask_log(sample))
