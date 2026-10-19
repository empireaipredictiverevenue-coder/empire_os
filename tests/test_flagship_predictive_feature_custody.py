"""Private prospective feature receipt safety and idempotency."""
from datetime import datetime,timezone
from pathlib import Path
from copy import deepcopy
import json
import os
import pytest

from empire_os.flagship_predictive_feature_custody import (
    FeatureCustodyHold, preserve_prospective_market_features,
    read_local_prospective_features,
)
from empire_os.flagship_market_knowledge_graph import build_market_knowledge_graph
from empire_os.flagship_predictive_market_features import build_point_in_time_market_features
from test_flagship_market_knowledge_graph import NOW,fixture


def sample(tmp_path):
    fixtures=tmp_path/"sources"
    fixture(fixtures)
    g=build_market_knowledge_graph(fixtures,as_of=NOW)
    return build_point_in_time_market_features(g,issued_at=NOW)


def test_no_write_without_explicit_capture(tmp_path):
    packet=sample(tmp_path)
    folder=tmp_path/"private/features"
    result=preserve_prospective_market_features(folder,packet)
    assert result["status"]=="PRIVATE_FEATURE_RECEIPT_PREVIEW_ONLY"
    assert result["written"] is False
    assert result["database_writes"] is False
    assert not folder.exists()


def test_capture_private_receipt_readback_and_replay_idempotent(tmp_path):
    packet=sample(tmp_path)
    folder=tmp_path/"features"
    captured=preserve_prospective_market_features(folder,packet,apply=True)
    assert captured["status"]=="PRIVATE_ORIGINAL_FEATURE_SNAPSHOT_RECORDED"
    assert captured["written"] is True
    assert captured["authenticated_production_registry"] is False
    assert folder.stat().st_mode&0o777==0o700
    path=folder/(packet["feature_packet_sha256"]+".json")
    assert path.stat().st_mode&0o777==0o600
    recovered=read_local_prospective_features(folder,packet["feature_packet_sha256"])
    assert recovered==packet
    replay=preserve_prospective_market_features(folder,packet,apply=True)
    assert replay["status"]=="EXACT_PRIOR_FEATURE_REPLAY"
    assert replay["written"] is False
    assert len(list(folder.iterdir()))==1


def test_tampered_hash_or_payload_blocks_prior_feature_persistence(tmp_path):
    packet=sample(tmp_path)
    packet["market_features"][0]["forecast_probability"]=0.8
    with pytest.raises(FeatureCustodyHold,match="untrusted"):
        preserve_prospective_market_features(tmp_path/"features",packet,apply=True)
    assert not (tmp_path/"features").exists()


def test_modified_saved_receipt_cannot_be_read(tmp_path):
    packet=sample(tmp_path)
    folder=tmp_path/"features"
    preserve_prospective_market_features(folder,packet,apply=True)
    path=folder/(packet["feature_packet_sha256"]+".json")
    document=json.loads(path.read_text())
    document["model_training_activated"]=True
    path.write_text(json.dumps(document)+"\n")
    with pytest.raises(FeatureCustodyHold):
        read_local_prospective_features(folder,packet["feature_packet_sha256"])


def test_world_readable_or_linked_features_held(tmp_path):
    packet=sample(tmp_path)
    folder=tmp_path/"features"
    preserve_prospective_market_features(folder,packet,apply=True)
    path=folder/(packet["feature_packet_sha256"]+".json")
    path.chmod(0o644)
    with pytest.raises(FeatureCustodyHold,match="original feature readback held"):
        read_local_prospective_features(folder,packet["feature_packet_sha256"])
    path.chmod(0o600)
    (tmp_path/"alias.json").hardlink_to(path)
    with pytest.raises(FeatureCustodyHold,match="original feature readback held"):
        read_local_prospective_features(folder,packet["feature_packet_sha256"])


def test_symlink_destination_not_allowed(tmp_path):
    packet=sample(tmp_path)
    folder=tmp_path/"features"
    folder.mkdir(mode=0o700)
    path=folder/(packet["feature_packet_sha256"]+".json")
    target=tmp_path/"sensitive"
    target.write_text("SENSITIVE")
    path.symlink_to(target)
    with pytest.raises(FeatureCustodyHold,match="unsafe"):
        preserve_prospective_market_features(folder,packet,apply=True)
    assert target.read_text()=="SENSITIVE"


def test_preexisting_conflicting_digest_held_without_overwrite(tmp_path):
    packet=sample(tmp_path)
    folder=tmp_path/"features"
    folder.mkdir(mode=0o700)
    path=folder/(packet["feature_packet_sha256"]+".json")
    path.write_text("existing other content")
    path.chmod(0o600)
    with pytest.raises(FeatureCustodyHold,match="conflicting"):
        preserve_prospective_market_features(folder,packet,apply=True)
    assert path.read_text()=="existing other content"


def test_readback_rejects_path_traversal_or_invalid_digest(tmp_path):
    folder=tmp_path/"features"
    for digest in ("../private", "a"*63, "A"*64, "foo@example.net"):
        with pytest.raises(FeatureCustodyHold,match="invalid feature"):
            read_local_prospective_features(folder,digest)
