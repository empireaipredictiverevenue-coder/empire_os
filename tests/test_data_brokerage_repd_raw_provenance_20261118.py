"""DESNZ raw publisher encoding, duplicate and source-provenance guards."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch
import csv,io,os,json
import pytest

from empire_os import data_brokerage_enterprise_feed as feed
from empire_os import predictive_cloud_prospective_outcome_eval as evaluate

NOW = "2027-02-09T11:15:00+00:00"
Q4 = "https://assets.publishing.service.gov.uk/media/abcdef123456/REPD_Publication_Q4_2026.csv"

def publisher_raw(n=10000,conflict=False):
    h=["Ref ID","Site Name","Technology Type","Development Status",
       "Record Last Updated (dd/mm/yyyy)","Installed Capacity (MWelec)",
       "County","Region","Country","Planning Authority","Planning Application Reference"]
    s=io.StringIO(newline="")
    w=csv.DictWriter(s,fieldnames=h)
    w.writeheader()
    for i in range(n):
        w.writerow({"Ref ID":str(i+10000),
                    "Site Name":"Bishop’s Waltham Solar Farm" if i==7 else f"Site {i}",
                    "Technology Type":"Solar Photovoltaics",
                    "Development Status":"Planning Application Submitted",
                    "Record Last Updated (dd/mm/yyyy)":"01/12/2026",
                    "Installed Capacity (MWelec)":"5.0","County":"Surrey",
                    "Region":"South East","Country":"England",
                    "Planning Authority":"Local Council",
                    "Planning Application Reference":"A/21/9"})
    if conflict:
        w.writerow({"Ref ID":"10007","Site Name":"DIVERGENT",
                    "Technology Type":"Solar Photovoltaics",
                    "Development Status":"Planning Permission Granted",
                    "Record Last Updated (dd/mm/yyyy)":"01/12/2026"})
    else:
        w.writerow({"Ref ID":"10007","Site Name":"Bishop’s Waltham Solar Farm",
                    "Technology Type":"Solar Photovoltaics",
                    "Development Status":"Planning Application Submitted",
                    "Record Last Updated (dd/mm/yyyy)":"01/12/2026",
                    "Installed Capacity (MWelec)":"5.0","County":"Surrey",
                    "Region":"South East","Country":"England",
                    "Planning Authority":"Local Council",
                    "Planning Application Reference":"A/21/9"})
    return s.getvalue().encode("cp1252")


def test_canonical_raw_source_corrects_cp1252_while_preserving_exact_duplicate():
    raw=publisher_raw()
    rows,meta=feed._parse_repd_raw(raw,NOW)
    assert len(rows)==10000 and meta["raw_publisher_row_count"]==10001
    assert meta["exact_duplicate_public_ref_rows"]==1
    assert meta["raw_publisher_encoding"]=="cp1252"
    assert next(x for x in rows if x["project_ref"]=="10007")["site_name"]=="Bishop’s Waltham Solar Farm"
    assert "�" not in next(x for x in rows if x["project_ref"]=="10007")["site_name"]
    assert all(x["observed_at"]==NOW for x in rows)


def test_conflicting_duplicate_project_ref_is_rejected_not_first_wins():
    with pytest.raises(ValueError,match="CONFLICTING_DUPLICATE"):
        feed._parse_repd_raw(publisher_raw(conflict=True),NOW)


def test_private_q4_raw_bytes_and_normalized_cloud_sha_match(tmp_path):
    root=tmp_path
    raw=publisher_raw()
    rows,quality=feed._parse_repd_raw(raw,NOW)
    digest=sha256(raw).hexdigest()
    relative=("runtime/predictive_cloud/brokerage_research_private/forecast_pilot/"
              f"source_archives/source_REPD_Publication_Q4_2026_{digest}.csv")
    f=root/relative
    f.parent.mkdir(parents=True,mode=0o700)
    with f.open("xb") as output:output.write(raw)
    os.chmod(f,0o600)
    source={
        "source_url":Q4,
        "source_snapshot_sha256":sha256(feed._csv_bytes(
            "uk_renewable_development_projects",rows)).hexdigest(),
        "publisher_publication_metadata":{
            "publisher_original_raw_sha256":digest,
            "publisher_original_raw_archive_relative":relative,
            "publisher_original_raw_bytes":len(raw),
            "publisher_original_source_url":Q4,
            "publisher_raw_redistribution_authorized":False,
            "publisher_source_content_addressed":True,
            "raw_publisher_encoding":"cp1252",
            "raw_publisher_row_count":10001,
            "exact_duplicate_public_ref_rows":1,
        },
    }
    ok=evaluate._verify_official_q4_raw_source(root,source,rows)
    assert ok["original_official_publisher_csv_sha256"]==digest
    assert ok["official_byte_to_normalized_cloud_fields_reconciled"]
    assert ok["original_publisher_exact_duplicate_ids"]==1
    assert ok["raw_source_redistribution_authorized"] is False
    # The Q1 2026 official archive used lowercase publication; the next
    # official publisher might do the same without changing source identity.
    lower_url=Q4.replace("REPD_Publication", "REPD_publication")
    lower_relative=relative.replace("REPD_Publication", "REPD_publication")
    lower_file=root/lower_relative
    with lower_file.open("xb") as output:output.write(raw)
    os.chmod(lower_file,0o600)
    lower_source=dict(source)
    lower_source["source_url"]=lower_url
    lower_meta=dict(source["publisher_publication_metadata"])
    lower_meta["publisher_original_raw_archive_relative"]=lower_relative
    lower_meta["publisher_original_source_url"]=lower_url
    lower_source["publisher_publication_metadata"]=lower_meta
    assert evaluate._verify_official_q4_raw_source(root,lower_source,rows)["original_official_publisher_csv_sha256"]==digest
    modified=dict(source)
    modified["source_snapshot_sha256"]="f"*64
    with pytest.raises(ValueError,match="NORMALISED_SOURCE_SHA_DRIFT"):
        evaluate._verify_official_q4_raw_source(root,modified,rows)
    f.write_bytes(raw+b" ")
    with pytest.raises(ValueError,match="FROZEN_RESEARCH_SHA_MISMATCH"):
        evaluate._verify_official_q4_raw_source(root,source,rows)


def test_missing_original_publisher_binary_never_admits_a_future_result(tmp_path):
    rows,_=feed._parse_repd_raw(publisher_raw(),NOW)
    with pytest.raises(ValueError,match="ARCHIVE_METADATA_HOLD"):
        evaluate._verify_official_q4_raw_source(
            tmp_path,{"source_url":Q4,
                      "source_snapshot_sha256":"1"*64},rows)
