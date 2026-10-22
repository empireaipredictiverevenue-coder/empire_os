import json
import pytest
from empire_os.youtube_transcript_recovery import retrieve_public_captions

ID = "4-t2SYWqDFw"
URL = "https://www.youtube.com/api/timedtext?foo=bar"

def page():
    return ('"captionTracks":' + json.dumps([{"baseUrl": URL, "languageCode": "en", "kind":"asr"}]) +
            ',"audioTracks"').encode()

def test_xml_caption_success():
    def fetch(url, timeout):
        return page() if "watch?v=" in url else b'<transcript><text>Get quotes</text><text>Sell results</text></transcript>'
    r = retrieve_public_captions(ID, fetch=fetch)
    assert r["status"] == "OK"
    assert "Get quotes" in r["text"]

def test_youtube_empty_caption_is_failure():
    def fetch(url, timeout):
        return page() if "watch?v=" in url else b""
    r = retrieve_public_captions(ID, fetch=fetch)
    assert r["status"] == "UNAVAILABLE"
    assert "empty body" in r["reason"]

def test_json_caption_success():
    def fetch(url, timeout):
        return page() if "watch?v=" in url else b'{"events":[{"segs":[{"utf8":"A real quote"}]}]}'
    assert retrieve_public_captions(ID, fetch=fetch)["text"] == "A real quote"

def test_invalid_source_rejected():
    with pytest.raises(ValueError):
        retrieve_public_captions("https://example.com/watch?v=4-t2SYWqDFw")

def test_no_tracks_reports_missing():
    r = retrieve_public_captions(ID, fetch=lambda url, timeout: b"no tracks")
    assert r["status"] == "UNAVAILABLE"
