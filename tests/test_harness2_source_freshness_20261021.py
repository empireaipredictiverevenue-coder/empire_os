"""Reject fabricated source timing without treating timestamps as authentication."""
from datetime import datetime,timedelta,timezone
import pytest
from empire_os.system_improvement_review import verify_review_source_freshness

NOW=datetime(2026,10,21,14,0,tzinfo=timezone.utc)

@pytest.mark.parametrize("kind,field",[
    ("conversion","observed_at"),("acquisition","generated_at"),("revenue","generated_at")
])
def test_exact_boundaries_and_times_are_source_only(kind,field):
    for t in (NOW,NOW-timedelta(minutes=60),NOW-timedelta(seconds=10)):
        status=verify_review_source_freshness(kind,{field:t.isoformat()},now=NOW)
        assert status['fresh_at_review'] is True
        assert status['source_authenticity_independently_verified'] is False
        assert status['execution_authority']=='none'

@pytest.mark.parametrize("delta",[
    timedelta(seconds=1),timedelta(minutes=60,seconds=1),timedelta(days=1),
])
def test_unapproved_future_or_expired_source_rejected(delta):
    with pytest.raises(ValueError):
        verify_review_source_freshness('revenue',{
            'generated_at':(NOW+delta if delta.total_seconds()==1
                            else NOW-delta).isoformat()},now=NOW)

@pytest.mark.parametrize("value",[
    None,42,True,"","2026-10-21T14:00:00",
    "invalid","2026-10-21T14:00:00+99:00",
])
def test_missing_or_unbounded_time_rejected(value):
    with pytest.raises(ValueError):
        verify_review_source_freshness('conversion',{'observed_at':value},now=NOW)

def test_max_age_and_evaluation_time_validated():
    with pytest.raises(ValueError):
        verify_review_source_freshness('conversion',{
            'observed_at':NOW.isoformat()},now=NOW.replace(tzinfo=None))
    with pytest.raises(ValueError):
        verify_review_source_freshness('conversion',{
            'observed_at':NOW.isoformat()},now=NOW,max_age_seconds=True)
