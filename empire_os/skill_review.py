"""Conservative static review of local skill metadata; no execution or approval."""
from __future__ import annotations
from pathlib import Path
import re
from empire_os.skill_exchange import SAFE_NAME, SKILLS_ROOT

LICENSE_LINE = re.compile(r'^license:\s*(.+)$', re.I | re.M)
BRAND_REFERENCES = ('anthropic', 'claude', 'openai brand', 'google brand')

def review_local_skill(name: str, *, root: Path = SKILLS_ROOT) -> dict:
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        return {'name': str(name), 'status': 'blocked', 'reasons': ['invalid_name']}
    path = root / name / 'SKILL.md'
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        return {'name': name, 'status': 'blocked', 'reasons': ['missing_or_unsafe_path']}
    if path.stat().st_size > 128_000:
        return {'name': name, 'status': 'blocked', 'reasons': ['oversize']}
    try:
        text = path.read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        return {'name': name, 'status': 'blocked', 'reasons': ['unreadable']}
    match = LICENSE_LINE.search(text[:4000])
    license_text = match.group(1).strip() if match else None
    reasons = []
    if not license_text:
        reasons.append('license_not_declared')
    elif 'proprietary' in license_text.lower():
        reasons.append('proprietary_license_requires_review')
    elif 'license.txt' in license_text.lower():
        reasons.append('license_file_requires_review')
    if name == 'brand-guidelines' and any(x in text.lower() for x in BRAND_REFERENCES):
        reasons.append('third_party_brand_instructions')
    # Static screening is not a malware, licence, or prompt-injection clearance.
    return {'name': name, 'status': 'manual_review_required',
            'license_declaration': license_text, 'reasons': reasons or ['manual_security_review_required'],
            'approved': False, 'execution_authority': 'none'}
