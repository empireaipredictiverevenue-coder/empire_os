"""Brave 422 validation must never be assumed to be an invalid key."""
from scripts.probe_brave_search_once_20261020 import assess_http_response

def test_explicit_subscription_token_invalid_is_diagnostic_not_guess():
    x=assess_http_response(422,{"error":{"code":"SUBSCRIPTION_TOKEN_INVALID",
                                             "detail":"SECRET VALUE MUST NEVER LEAK",
                                             "meta":{"component":"authentication"}}})
    assert x["state"]=="BRAVE_SUBSCRIPTION_TOKEN_INVALID"
    assert x["brave_error_code"]=="SUBSCRIPTION_TOKEN_INVALID"
    assert "SECRET VALUE" not in str(x)
    assert x["result_count"]==0

def test_validation_422_is_not_mislabeled_auth():
    x=assess_http_response(422,{"error":{"code":"VALIDATION_ERROR",
                                             "meta":{"component":"validation"}}})
    assert x["state"]=="BRAVE_REQUEST_VALIDATION_ERROR"

def test_unknown_422_requires_review_not_fake_auth_claim():
    x=assess_http_response(422,{"error":{"code":"NOT_PROVIDED",
                                             "detail":"abc"}})
    assert x["state"]=="BRAVE_PROVIDER_HTTP_FAILURE_NOT_YET_CLASSIFIED"
    assert x["brave_error_code"]=="OTHER_OR_UNSPECIFIED_ERROR"
    assert x["api_key_value_logged"] is False

def test_non_string_provider_meta_failclosed():
    x=assess_http_response(422,{"error":{"code":"INVALID_ARGUMENT",
                                             "meta":{"component":["SECRET"]}}})
    assert x["brave_error_component"]=="not_specified"
