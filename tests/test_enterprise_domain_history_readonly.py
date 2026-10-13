"""Canonical enterprise history is bounded and cannot clear outbound."""
import pytest

from empire_os.enterprise_domain_history_readonly import inspect_domains
from scripts.inspect_enterprise_review_domain_history_readonly import domains_from_review


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self, rows):
        self.cur = FakeCursor(rows)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self):
        return self.cur


def test_domain_history_is_parameterized_read_only_and_never_send_clearance():
    conn = FakeConnection([("blackstone.com", True, False, False),
                           ("championsgroupholdings.com", False, False, True)])
    result = inspect_domains(
        "fixture-dsn", ["championsgroupholdings.com", "blackstone.com"],
        connect_factory=lambda dsn: conn,
    )
    assert result["domain_count"] == 2
    assert result["database_writes"] is False
    assert result["outbound_sent"] is False
    assert result["individual_recipient_suppression_cleared"] is False
    assert result["founder_send_authorized"] is False
    assert result["domain_results"]["blackstone.com"]["prior_canonical_intent_observed"] is True
    assert result["domain_results"]["championsgroupholdings.com"]["any_suppression_on_domain_observed"] is True
    assert all(r["individual_recipient_suppression_cleared"] is False for r in result["domain_results"].values())
    assert conn.cur.executed[0][0] == "SET TRANSACTION READ ONLY"
    assert conn.cur.executed[-1][0] == "ROLLBACK"
    assert conn.cur.executed[2][1] == (["blackstone.com", "championsgroupholdings.com"],)


def test_even_negative_domain_history_never_grants_clearance():
    result = inspect_domains("fixture", ["championsgroupholdings.com"],
                             connect_factory=lambda _: FakeConnection([
                                 ("championsgroupholdings.com", False, False, False)
                             ]))
    entry = result["domain_results"]["championsgroupholdings.com"]
    assert entry["domain_contact_history_state"] == "NO_DOMAIN_HISTORY_OBSERVED_NOT_SEND_CLEARANCE"
    assert entry["outreach_authorized"] is False
    assert entry["individual_recipient_suppression_cleared"] is False


def test_bad_dsn_domains_or_bad_reader_shape_fail_closed():
    with pytest.raises(ValueError):
        inspect_domains("", ["championsgroupholdings.com"])
    with pytest.raises(ValueError):
        inspect_domains("fixture", ["championsgroupholdings.com", "championsgroupholdings.com"])
    with pytest.raises(ValueError):
        inspect_domains("fixture", ["'; DROP TABLE intents; --"])
    with pytest.raises(ValueError):
        inspect_domains("fixture", ["championsgroupholdings.com"],
                        connect_factory=lambda _: FakeConnection([
                            ("championsgroupholdings.com", 0, False, False)
                        ]))


def test_sponsor_domain_joins_curated_seed_without_account_merge():
    review = {"mode": "OBSERVE", "outreach_authorized": False, "packets": [
        {"domain": "championsgroupholdings.com", "outreach_authorized": False,
         "sponsor_account_overlap_review": {"related_seed_accounts": [
             {"account_key": "blackstone_operating_team"}
         ]}}
    ]}
    assert domains_from_review(review) == ["blackstone.com", "championsgroupholdings.com"]
    review["packets"][0]["sponsor_account_overlap_review"]["related_seed_accounts"] = [
        {"account_key": "unregistered_group"}
    ]
    with pytest.raises(ValueError, match="UNRESOLVED_SPONSOR_ACCOUNT"):
        domains_from_review(review)
