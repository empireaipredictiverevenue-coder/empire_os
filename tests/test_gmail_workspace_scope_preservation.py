"""The existing sending transport preserves additional inbox-read consent."""
import json

from empire_os.gmail_api_transport import GMAIL_SEND_SCOPE, load_gmail_credentials
from empire_os.google_workspace_mailbox import READ_SCOPE


def test_oauth_refresh_preserves_additional_granted_scopes(tmp_path, monkeypatch):
    path = tmp_path / "workspace-token.json"
    path.write_text("{}")
    class FakeCredentials:
        expired = True
        refresh_token = "fixture"
        scopes = [GMAIL_SEND_SCOPE, READ_SCOPE]
        valid = True
        def refresh(self, request):
            self.expired = False
        def to_json(self):
            return json.dumps({"scopes": self.scopes})
    from google.oauth2.credentials import Credentials
    monkeypatch.setattr(Credentials, "from_authorized_user_file",
                        staticmethod(lambda filepath: FakeCredentials()))
    result = load_gmail_credentials(path)
    assert result.scopes == [GMAIL_SEND_SCOPE, READ_SCOPE]
    assert json.loads(path.read_text())["scopes"] == result.scopes
    assert oct(path.stat().st_mode & 0o777) == "0o600"
