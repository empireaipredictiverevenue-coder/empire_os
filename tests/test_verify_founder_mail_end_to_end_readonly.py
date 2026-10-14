"""Founder mail verification is honest about provider identity and replies."""
from scripts.verify_founder_mail_end_to_end_readonly import assess


def fixture():
    return dict(
        relay={"ok": True, "provider": "gmail_api", "send_authorized": False},
        identity={"founder_sender_config_matches": True,
                  "reply_to_config_matches": True,
                  "relay_observe_mode": True,
                  "relay_send_authorized": False},
        token={"token_active_at_google": True,
               "gmail_send_scope_verified": True,
               "founder_google_account_identity_verified": False},
        imap={"provider": "owned_imap", "configured": False},
        inbound={"ok": True, "provider": "resend"},
        root_mx=["1 smtp.google.com."],
        sub_mx=["10 inbound-smtp.us-east-1.amazonaws.com."],
        sub_txt=["v=DMARC1; p=none"],
    )


def test_live_2026_mail_split_fails_closed_despite_valid_oauth():
    p = assess(**fixture())
    assert p["smtp_sender_configured_for_founder"] is True
    assert p["reply_to_configured_for_founder"] is True
    assert p["gmail_send_permission_verified"] is True
    assert p["google_token_verified"] is True
    assert p["gmail_account_identity_verified"] is False
    assert p["founder_imap_configured"] is False
    assert p["root_domain_mx_google"] is True
    assert p["reply_subdomain_mx_amazon_ses"] is True
    assert p["resend_inbound_webhook_service_active"] is True
    assert "PUBLIC_REPLY_MX_AND_INBOUND_WEBHOOK_PROVIDER_MISMATCH" in p["readiness_blockers"]
    assert p["ready_for_prospect_outbound"] is False
    assert p["ready_for_internal_mail_test"] is False
    assert p["outbound_sent"] is False
    assert p["dns_modified"] is False


def test_missing_relay_and_oauth_fail_closed():
    args = fixture()
    args["relay"] = {}
    args["identity"] = {}
    args["token"] = {}
    p = assess(**args)
    assert "LIVE_FOUNDER_SENDER_OR_REPLY_IDENTITY_UNVERIFIED" in p["readiness_blockers"]
    assert "GOOGLE_GMAIL_SEND_OAUTH_UNVERIFIED" in p["readiness_blockers"]
    assert p["ready_for_prospect_outbound"] is False


def test_aligned_dns_and_config_still_require_real_reply_evidence():
    args = fixture()
    args["token"]["founder_google_account_identity_verified"] = True
    args["imap"] = {"provider": "owned_imap", "configured": True}
    args["inbound"] = {"ok": False, "provider": "owned_imap"}
    args["sub_mx"] = ["1 smtp.google.com."]
    args["sub_txt"] = ['"v=spf1 include:_spf.google.com -all"']
    p = assess(**args)
    assert p["reply_subdomain_mx_amazon_ses"] is False
    assert p["founder_imap_configured"] is True
    assert p["reply_subdomain_spf_present"] is True
    assert p["readiness_blockers"] == ["INDEPENDENT_END_TO_END_SEND_AND_REPLY_NOT_VERIFIED"]
    assert p["ready_for_prospect_outbound"] is False


def test_no_credentials_or_recipient_values_emitted():
    p = assess(**fixture())
    text = str(p)
    assert "refresh_token" not in text
    assert "client_secret" not in text
    assert "oauth2.googleapis.com" not in text
    assert "flavag83" not in text


def test_verified_workspace_reader_avoids_false_missing_imap_blocker():
    args = fixture()
    args["imap"] = {"provider": "google_workspace", "configured": True}
    args["token"]["founder_google_account_identity_verified"] = True
    proof = assess(**args)
    assert proof["founder_workspace_reader_configured"] is True
    assert proof["founder_imap_configured"] is False
    assert "FOUNDER_READ_INBOX_NOT_CONFIGURED" not in proof["readiness_blockers"]
    assert "REPLY_SUBDOMAIN_STILL_ROUTES_TO_AMAZON_SES" in proof["readiness_blockers"]
    assert proof["ready_for_prospect_outbound"] is False


def test_live_relay_uses_existing_durable_workspace_oauth_not_legacy_testing_token():
    from scripts.verify_founder_mail_end_to_end_readonly import TOKEN_PATH as proof_path
    from empire_os.google_workspace_mailbox import TOKEN_PATH as inbox_path
    assert proof_path.name == 'google-workspace-internal-token.json'
    assert inbox_path == proof_path
