from datetime import datetime, timezone
from scripts.poll_buyer_gmail_readonly import collect, READ_SCOPE

class Response:
    def execute(self):
        return {'messages': [{'id': 'abcdef1234567890', 'internalDate': '1791633600000', 'labelIds': ['INBOX'], 'payload': {'headers': [{'name': 'From', 'value': 'buyer@example.com'}]}}]}

class Threads:
    def get(self, **kwargs):
        assert kwargs['format'] == 'metadata'
        return Response()

class Users:
    def threads(self): return Threads()

class Service:
    def users(self): return Users()

def test_reader_metadata_contract():
    result = collect(Service(), now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert len(result['threads']) == 4
    assert sum(t['message_count'] for t in result['threads']) == 4
    assert 'body' not in result['threads'][0]['messages'][0]
    assert READ_SCOPE.endswith('gmail.readonly')
