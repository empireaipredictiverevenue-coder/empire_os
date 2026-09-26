from empire_os.search_fabric.decoder import extract_emails


def _cfemail(value: str, key: int = 0x12) -> str:
    data = bytes([key]) + bytes(ord(ch) ^ key for ch in value)
    return data.hex()


def test_extracts_bracket_obfuscated_email():
    html = "<p>Jane Smith — jane [at] acme [dot] com</p>"
    assert extract_emails(html) == ["jane@acme.com"]


def test_extracts_parenthesis_obfuscated_email():
    html = "<p>Contact jane (at) acme (dot) co.uk</p>"
    assert extract_emails(html) == ["jane@acme.co.uk"]


def test_extracts_cloudflare_protected_email():
    encoded = _cfemail("jane@acme.com")
    html = f'<a class="__cf_email__" data-cfemail="{encoded}">email protected</a>'
    assert extract_emails(html) == ["jane@acme.com"]


def test_deduplicates_normal_and_obfuscated_email():
    html = "jane@acme.com <span>jane [at] acme [dot] com</span>"
    assert extract_emails(html) == ["jane@acme.com"]
