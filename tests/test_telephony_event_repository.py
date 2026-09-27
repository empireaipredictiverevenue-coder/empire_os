from empire_os.telephony_event_repository import TelephonyEventRepository


class FakeGateway:
    def __init__(self):
        self.calls = []

    def insert(self, table, row, *, return_repr=True):
        self.calls.append((table, dict(row), return_repr))
        return []


def test_telephony_repository_records_call_through_gateway():
    gateway = FakeGateway()
    repository = TelephonyEventRepository(gateway)

    repository.record_call({
        "call_sid": "call-1",
        "status": "completed",
        "duration": 90,
    })

    assert gateway.calls == [(
        "call_logs",
        {
            "call_sid": "call-1",
            "status": "completed",
            "duration": 90,
        },
        False,
    )]
