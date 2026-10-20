from dataclasses import FrozenInstanceError
import pytest

from empire_os.consumer_optin_confirmation_email import render_first_party_confirmation

CONFIRM="https://empire-ai.co.uk/roofing/email-preferences#confirm="+"A"*43
STOP="https://empire-ai.co.uk/roofing/email-preferences#unsubscribe="+"B"*43


def test_template_is_own_brand_and_not_authorised_for_sending():
    msg=render_first_party_confirmation(recipient="only-for-test@example.test",
        confirm_link=CONFIRM,unsubscribe_link=STOP)
    assert msg.recipient=="only-for-test@example.test"
    assert msg.purpose=="EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES"
    assert not msg.send_authorized
    for output in (msg.text_body,msg.html_body):
        assert "empire-ai.co.uk" in output
        assert "contractor" in output
        assert "https://empire-ai.co.uk/privacy" in output
        assert "confirm" in output.lower()
        assert "unsubscribe" in output.lower() or "stop homeowner" in output.lower()
        assert "tracking" not in output.lower()
    with pytest.raises(FrozenInstanceError):
        msg.recipient="other@example.test"


@pytest.mark.parametrize("invalid",[
    "http://empire-ai.co.uk/roofing/email-preferences#confirm="+"A"*43,
    "https://evil.example/roofing/email-preferences#confirm="+"A"*43,
    "https://empire-ai.co.uk/roofing/email-preferences?token=bad#confirm="+"A"*43,
    "https://empire-ai.co.uk/roofing/email-preferences#unsubscribe="+"A"*43,
    "https://empire-ai.co.uk/roofing/email-preferences#confirm=short",
    'https://empire-ai.co.uk/roofing/email-preferences#confirm='+'A'*42+'">',
])
def test_untrusted_confirmation_links_rejected(invalid):
    with pytest.raises(ValueError):
        render_first_party_confirmation(recipient="only-for-test@example.test",
            confirm_link=invalid,unsubscribe_link=STOP)


def test_cross_purpose_unsubscribe_link_rejected():
    with pytest.raises(ValueError):
        render_first_party_confirmation(recipient="only-for-test@example.test",
            confirm_link=CONFIRM,unsubscribe_link=CONFIRM)


def test_no_marketing_subscriber_implied_by_rendering_template():
    msg=render_first_party_confirmation(recipient="only-for-test@example.test",
        confirm_link=CONFIRM,unsubscribe_link=STOP)
    assert msg.send_authorized is False
    assert "You won't be subscribed unless you confirm" in msg.text_body
    assert "does not authorise us to share" in msg.text_body
