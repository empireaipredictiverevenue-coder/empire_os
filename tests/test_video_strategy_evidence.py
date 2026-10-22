from empire_os.video_strategy_evidence import normalize_vtt, strategy_evidence
import pytest

def test_overlapping_autocaptions():
    s = ("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nWe get <c>quotes</c>\n\n"
         "00:00:01.000 --> 00:00:02.000\nWe get quotes from clients\n\n"
         "00:00:02.000 --> 00:00:03.000\nfrom clients every day\n")
    c = normalize_vtt(s)
    assert " ".join(x["text"] for x in c) == "We get quotes from clients every day"
    e = strategy_evidence(c, "4-t2SYWqDFw")
    assert e["topic_evidence"]["quote"]
    assert e["model_promotion_authorized"] is False

def test_missing_caption_rejected():
    with pytest.raises(ValueError):
        normalize_vtt("")

def test_video_id_rejected():
    with pytest.raises(ValueError):
        strategy_evidence([], "bad")
