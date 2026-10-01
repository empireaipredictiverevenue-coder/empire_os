"""Synthetic CSV fixtures only; no production evidence."""
import csv
import io
import json

import pytest

from empire_os.revenue_exchange_ingest import prepare_coverage_export
from empire_os.buyer_call_economics import build_call_economics
from empire_os.buyer_capacity_intake import parse_buyer_capacity_reply
from empire_os.buyer_commercial_terms_intake import parse_buyer_stated_price


HEADER = ['category', 'service', 'zipcode', 'city', 'state', 'expected_value']
ROW = ['Roofing', 'Repair', '00501', 'Holtsville', 'NY', '5.52']


def csv_bytes(rows, header=HEADER):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode()


def prepare(content):
    return prepare_coverage_export(content, source_ref='fixture:export',
                                   program_ref='fixture:affiliate')


def test_original_observations_duplicates_conflicts_and_leading_zero():
    result = prepare(csv_bytes([ROW, ROW, ROW[:-1] + ['13.75']]))
    assert result['summary'] == dict(rows=3, exact_distinct_rows=2,
                                   exact_duplicate_rows=1, zipcodes=1,
                                   differing_value_groups=1)
    first = result['observations'][0]
    assert first['source_fields'] == dict(zip(HEADER, ROW))
    assert first['occurrences'] == [dict(record=2, ending_line=2),
                                    dict(record=3, ending_line=3)]
    conflict = result['differing_values'][0]
    assert conflict['canonical_value'] is None
    assert [x['value'] for x in conflict['observations_by_value']] == ['5.52', '13.75']


def test_decimal_equivalence_is_not_exact_duplicate_or_conflict():
    result = prepare(csv_bytes([ROW, ROW[:-1] + ['5.520']]))
    assert result['summary']['exact_distinct_rows'] == 2
    assert result['summary']['exact_duplicate_rows'] == 0
    assert result['differing_values'] == []


@pytest.mark.parametrize('field,value', [
    ('zipcode', '501'), ('zipcode', '00501-1234'), ('zipcode', '００５０１'),
    ('state', 'New York'), ('state', ''), ('city', ' '), ('category', ''),
    ('service', '\x00'), ('expected_value', 'NaN'), ('expected_value', 'Infinity'),
    ('expected_value', '-1'), ('expected_value', '0'), ('expected_value', '$5.52'),
    ('expected_value', '1e9'), ('expected_value', '1_000'),
])
def test_invalid_fields_fail_closed(field, value):
    row = ROW.copy()
    row[HEADER.index(field)] = value
    with pytest.raises(ValueError, match='record 3:'):
        prepare(csv_bytes([ROW, row]))


@pytest.mark.parametrize('content', [b'', b'\xff', csv_bytes([]),
    csv_bytes([ROW[:-1]]), csv_bytes([ROW + ['extra']]),
    csv_bytes([ROW], HEADER[:-1] + ['city']),
    csv_bytes([ROW], HEADER + ['payout']),
    (','.join(HEADER) + '\n"unclosed').encode(),
])
def test_invalid_files_have_no_partial_packet(content):
    with pytest.raises(ValueError):
        prepare(content)


def test_idempotent_artifact_scoped_keys_and_provenance():
    content = csv_bytes([ROW, ROW])
    a = prepare(content)
    assert a == prepare(content)
    assert json.loads(json.dumps(a)) == a
    changed = prepare(csv_bytes([ROW[:-1] + ['7']]))
    assert changed['batch_key'] != a['batch_key']
    assert changed['observations'][0]['observation_key'] != a['observations'][0]['observation_key']
    other = prepare_coverage_export(content, source_ref='fixture:export', program_ref='other')
    assert other['batch_key'] != a['batch_key']
    assert len(a['source']['sha256']) == 64


def test_expected_values_cannot_supply_payable_terms_or_capacity():
    result = prepare(csv_bytes([ROW]))
    assert all(value is None for value in result['payable_terms'].values())
    assert result['commercial_channel'] == 'affiliate_calls'
    assert result['dry_run'] is True
    assert result['ingestion_ready'] is False
    assert result['live_traffic_authorized'] is False
    assert result['revenue_recognized'] is False
    assert result['observations'][0]['expected_value']['verified_payout'] is False
    assert 'verified_price_per_lead_cents' not in json.dumps(result)
    assert not parse_buyer_stated_price(json.dumps(result))['has_explicit_price_evidence']
    assert not parse_buyer_capacity_reply(json.dumps(result))['has_explicit_capacity_evidence']
    economics = build_call_economics(
        buyer_name='Lead Smart', program_ref='fixture', service='roofing',
        geography=None, payout_amount=None, payout_currency=None,
        qualification_seconds=None, daily_cap=None, traffic_source=None,
        traffic_source_approved=False, routing_mode=None, routing_verified=False,
        tracking_verified=False, buyer_asset_approved=False)
    assert not economics['pilot_ready']
    assert economics['economics']['gross_margin_per_accepted_call'] is None


def test_provenance_is_required():
    with pytest.raises(ValueError, match='source_ref'):
        prepare_coverage_export(csv_bytes([ROW]), source_ref='', program_ref='test')
    with pytest.raises(ValueError, match='program_ref'):
        prepare_coverage_export(csv_bytes([ROW]), source_ref='test', program_ref='')


def test_reordered_header_and_bom_preserve_fields():
    result = prepare(b'\xef\xbb\xbf' + csv_bytes([list(reversed(ROW))], list(reversed(HEADER))))
    assert result['observations'][0]['source_fields'] == dict(zip(HEADER, ROW))
