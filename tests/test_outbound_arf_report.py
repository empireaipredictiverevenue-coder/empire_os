from empire_os.outbound_arf_report import parse_arf_report


def test_parse_arf_abuse_report():
    raw = """From: fbl@example.test
Content-Type: multipart/report; report-type=feedback-report; boundary=abc

--abc
Content-Type: text/plain

Complaint report
--abc
Content-Type: message/feedback-report

Feedback-Type: abuse
User-Agent: ExampleFBL/1.0
Original-Mail-From: sender@example.com
Original-Rcpt-To: user@example.net
Source-IP: 192.0.2.1
Reported-Domain: example.com

--abc--
"""
    result = parse_arf_report(raw)
    assert result["is_arf"] is True
    assert result["feedback_type"] == "abuse"
    assert result["complaint"] is True
