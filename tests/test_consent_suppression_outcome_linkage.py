# EMPIRE_WAVE_090C_D1
from empire_os.consent_suppression_outcome_linkage import (
    classify_outcome,
    trace_values,
)


def test_unsubscribe_event():

    assert (
        classify_outcome(
            {
                "event_type":
                    "unsubscribe",
            }
        )
        == "UNSUBSCRIBE_OPT_OUT"
    )


def test_boolean_bounce_event():

    assert (
        classify_outcome(
            {
                "is_bounced":
                    True,
            }
        )
        == "BOUNCE"
    )


def test_reply_event():

    assert (
        classify_outcome(
            {
                "status":
                    "replied",
            }
        )
        == "REPLY"
    )


def test_non_outcome_is_none():

    assert (
        classify_outcome(
            {
                "status":
                    "queued",
            }
        )
        is None
    )


def test_trace_keys():

    result = trace_values(
        {
            "message_id":
                "abc",

            "thread_id":
                "xyz",
        }
    )

    assert (
        "message_id",
        "abc",
    ) in result
