"""Large PostgreSQL COPY files: bounded streaming and no personal-data export."""
from __future__ import annotations
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
import json
import pytest

from empire_os.jev_large_prospect_dump_reader import scan_prospect_copy_stream

ROOT=Path(__file__).resolve().parents[1]
LIVE=Path("/srv/empire_os/runtime/data_cloud")
COLUMNS=("id","created_at","business_name","niche","metro","phone",
         "website","address","rating","review_count","buy_signal_score",
         "runs_ads","status","notes","contacted_at","contact_name",
         "contact_title","contact_source","contacted_status")


def fixture(path:Path, size:int=3, *, invalid:bool=False)->tuple[int,dict]:
    marker = (
        'COPY "public"."prospects" ('+
        ", ".join(f'"{column}"' for column in COLUMNS)+
        ') FROM stdin;\n'
    )
    ids=[]
    with path.open("wb") as f:
        f.write(b"SET session_replication_role = replica;\n")
        f.write(b'COPY "auth"."users" ("id", "email") FROM stdin;\n')
        f.write(b"not-a-prospect\tsensitive@example.invalid\n\\.\n")
        f.write(marker.encode("ascii"))
        for n in range(size):
            ids.append(f"00000000-0000-0000-0000-{n:012d}")
            values=[
                ids[-1],"2026-10-21 10:00:00+00","PRIVATE ACCOUNT","roofing",
                "Chicago","private@example.invalid","private.com",
                "ONE PRIVATE STREET","4.2","50","1.0","f","converted",
                "PRIVATE NOTES","\\N","PRIVATE NAME","PRIVATE ROLE",
                "private source","CONTACTED",
            ]
            if invalid and n==1:
                values=values[:-1]
            f.write(("\t".join(values)+"\n").encode())
        f.write(b"\\.\n")
        f.write(b'COPY "storage"."objects" ("id") FROM stdin;\n')
        f.write(b"private-object-id\n\\.\n")
    digest=sha256()
    for pk in sorted(ids):
        digest.update(pk.encode())
        digest.update(b"\n")
    proof={
        "verified":True,"source_rows":size,"target_rows":size,
        "source_pk_sha256":digest.hexdigest(),
        "target_pk_sha256":digest.hexdigest(),
    }
    return size,proof


def test_local_synthetic_dump_is_verified_without_exporting_any_sensitive_field(tmp_path):
    p=tmp_path/"source.sql"
    rows,proof=fixture(p,100)
    evidence=scan_prospect_copy_stream(p,historical=proof)
    assert evidence["source_counted_copy_rows"]==100
    assert evidence["historical_independent_id_set_match"] is True
    assert evidence["niche_aggregate_counts"]=={"roofing":100}
    assert evidence["metro_aggregate_counts"]=={"chicago":100}
    assert evidence["monthly_cohort_counts"]=={"2026-10":100}
    assert evidence["status_counts_unverified"]=={"converted_status_unverified":100}
    assert evidence["commercial_leads_authorized"]==0
    assert evidence["model_records_processed"]==0
    assert evidence["all_source_rows_in_memory"] is False
    assert evidence["source_contacts_or_names_exported"] is False
    assert evidence["database_writes"] is False
    output=json.dumps(evidence)
    for secret in ("private@example.invalid","PRIVATE ACCOUNT","ONE PRIVATE STREET",
                   "PRIVATE NOTES","PRIVATE NAME","private-object-id","private.com"):
        assert secret not in output


def test_oversized_dump_rows_are_bounded(tmp_path):
    p=tmp_path/"oversized.sql"
    p.write_bytes(b"COPY \"public\".\"prospects\" (id, created_at, niche, metro, status) FROM stdin;\n"
                  +b"x"*140000+b"\n\\.\n")
    with pytest.raises(ValueError,match="oversized"):
        scan_prospect_copy_stream(p)


def test_malformed_copy_record_rejected(tmp_path):
    p=tmp_path/"malformed.sql"
    fixture(p,3,invalid=True)
    with pytest.raises(ValueError,match="column count"):
        scan_prospect_copy_stream(p)


def test_duplicate_copy_block_rejected(tmp_path):
    p=tmp_path/"duplicate.sql"
    fixture(p,1)
    tail=p.read_bytes().split(b'COPY "public"."prospects" ',1)[1].split(
        b'COPY "storage"."objects"',1)[0]
    with p.open("ab") as f:
        f.write(b'COPY "public"."prospects" '+tail)
    with pytest.raises(ValueError,match="duplicate"):
        scan_prospect_copy_stream(p)


def test_historical_identity_hash_is_required(tmp_path):
    p=tmp_path/"hash_mismatch.sql"
    size,proof=fixture(p,20)
    proof["source_pk_sha256"]="f"*64
    proof["target_pk_sha256"]="f"*64
    with pytest.raises(ValueError,match="does not match"):
        scan_prospect_copy_stream(p,historical=proof)


def test_source_with_historical_row_mismatch_fails(tmp_path):
    p=tmp_path/"bad_count.sql"
    size,proof=fixture(p,15)
    proof["source_rows"]=size+1
    proof["target_rows"]=size+1
    with pytest.raises(ValueError,match="does not match"):
        scan_prospect_copy_stream(p,historical=proof)


def test_symlinked_copy_file_rejected(tmp_path):
    p=tmp_path/"original.sql"
    fixture(p,3)
    alias=tmp_path/"alias.sql"
    alias.symlink_to(p)
    with pytest.raises(ValueError,match="regular"):
        scan_prospect_copy_stream(alias)


def test_row_budget_and_digest_tracking_bounds(tmp_path):
    p=tmp_path/"limits.sql"
    size,proof=fixture(p,33)
    with pytest.raises(ValueError,match="row budget"):
        scan_prospect_copy_stream(p,max_rows=30)
    unverified=scan_prospect_copy_stream(p,tracked_id_limit=3)
    assert unverified["source_counted_copy_rows"]==33
    assert unverified["historical_digest_track_limit_reached"] is True
    assert unverified["historical_independent_id_set_match"] is False
    with pytest.raises(ValueError,match="does not match"):
        scan_prospect_copy_stream(p,historical=proof,tracked_id_limit=3)


def test_large_synthetic_sample_is_streamed_without_raw_record_collection(tmp_path):
    p=tmp_path/"synthetic_25000.sql"
    size,proof=fixture(p,25_000)
    report=scan_prospect_copy_stream(p,historical=proof)
    assert report["source_counted_copy_rows"]==25_000
    assert report["historical_independent_id_set_match"] is True
    assert report["source_size_bytes"]==p.stat().st_size
    assert report["niche_aggregate_counts"]=={"roofing":25_000}


def test_real_historical_234mb_prospect_dump_matches_verified_copy_checksum():
    p=LIVE/"supabase_public_data.sql"
    if not p.is_file():
        pytest.skip("live source not mounted")
    verification=json.loads((LIVE/"shadow_independent_verify_latest.json").read_text())
    proof=next(row for row in verification["tables"] if row["table"]=="prospects")
    report=scan_prospect_copy_stream(p,historical=proof)
    assert report["source_counted_copy_rows"]==32899
    assert report["historical_independent_id_set_match"] is True
    assert report["source_contacts_or_names_exported"] is False
    assert report["model_records_processed"]==0


def test_committed_offline_stream_receipt_is_aggregate_only():
    file=ROOT/"docs/commercial/JEV_LARGE_PROSPECT_DUMP_STREAM_20261021.json"
    report=json.loads(file.read_text())
    assert report["schema_version"]=="empire.jev.large_prospect_copy_stream.v1"
    assert report["source_counted_copy_rows"]==32899
    assert report["source_size_bytes"]==233910763
    assert report["historical_independent_id_set_match"] is True
    assert report["niche_aggregate_counts"]["roofing"]==3674
    assert report["niche_aggregate_counts"]["commercial_roofing"]==2035
    assert report["niche_aggregate_counts"]["other_or_unmapped"]==2913
    assert sum(report["niche_aggregate_counts"].values())==32899
    assert sum(report["monthly_cohort_counts"].values())+report["unknown_or_invalid_created_month_rows"]==32899
    assert sum(report["metro_aggregate_counts"].values())==32899
    assert report["source_contacts_or_names_exported"] is False
    assert report["commercial_leads_authorized"]==0
    assert report["model_records_processed"]==0
    assert report["outreach_sent"]==0
    assert report["database_writes"] is False
    assert report["execution_authority"]=="none"
    document=file.read_text()
    assert "@" not in document
    assert "contact_name" not in document
    assert "contact_email" not in document
    assert "prospect_id" not in document
    assert "private.example" not in document
