"""First-party transactional *template*, not an email sender.

No tracking pixels, no scraped contacts, no buyer promotions, and no
auto-opt-in. Private delivery service must first enforce approved sender,
consent receipt, recipient verification and suppression.
"""
from __future__ import annotations
from dataclasses import dataclass
from html import escape
from urllib.parse import urlsplit

from empire_os.consumer_optin_token_security import canonical_email

ORIGIN = "https://empire-ai.co.uk"
PREFERENCE_PAGE = "/roofing/email-preferences"


@dataclass(frozen=True)
class VerificationMessage:
    recipient: str
    subject: str
    text_body: str
    html_body: str
    purpose: str = "EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES"
    send_authorized: bool = False


def _valid_private_link(url: str, purpose: str) -> bool:
    if not isinstance(url, str) or len(url) > 400:
        return False
    parts=urlsplit(url)
    expected_fragment = ("confirm=" if purpose=="confirm" else
                         "unsubscribe=" if purpose=="unsubscribe" else "")
    if (parts.scheme!="https" or parts.netloc!="empire-ai.co.uk"
        or parts.path!=PREFERENCE_PAGE or parts.query
        or not parts.fragment.startswith(expected_fragment)):
        return False
    token=parts.fragment.removeprefix(expected_fragment)
    return len(token)==43 and all(c in
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for c in token)


def render_first_party_confirmation(
    *, recipient: str, confirm_link: str, unsubscribe_link: str,
) -> VerificationMessage:
    contact=canonical_email(recipient)
    if (not _valid_private_link(confirm_link,"confirm")
        or not _valid_private_link(unsubscribe_link,"unsubscribe")
        or confirm_link==unsubscribe_link):
        raise ValueError("unsigned or unapproved first-party link")
    subject="Confirm your optional Empire AI homeowner updates"
    text=(
        "You requested optional homeowner guides and updates from Empire AI.\n\n"
        "Please confirm that you want these emails:\n"
        +confirm_link+"\n\n"
        "If you didn't request them, ignore this email. You won't be "
        "subscribed unless you confirm.\n\n"
        "You can also stop updates using this link:\n"
        +unsubscribe_link+"\n\n"
        "This request does not authorise us to share your contact details "
        "with roofing contractors or other buyers.\n"
        "Privacy: https://empire-ai.co.uk/privacy\n"
        "Empire AI · https://empire-ai.co.uk\n"
    )
    html=(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '</head><body style="font-family:Arial,sans-serif;color:#0c2749">'
        '<h1>Confirm your homeowner updates</h1>'
        '<p>You requested optional guides and updates from Empire AI.</p>'
        '<p><a href="'+escape(confirm_link,quote=True)+'">Confirm my subscription</a></p>'
        "<p>If you didn't ask, ignore this email. You won't be subscribed unless you confirm.</p>"
        '<p><a href="'+escape(unsubscribe_link,quote=True)+'">Stop homeowner updates</a></p>'
        '<p>We have not asked to share your contact details with contractors or other buyers.</p>'
        '<p><a href="https://empire-ai.co.uk/privacy">Privacy notice</a> · '
        'Empire AI</p></body></html>'
    )
    return VerificationMessage(
        recipient=contact,subject=subject,text_body=text,html_body=html,
    )
