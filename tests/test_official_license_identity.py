from empire_os.official_license_identity import texas_rmp_seeds_from_csv

CSV = """RANK,LICENSE_NBR,LIC_STATUS,LICENSE_DATE,EXPIRATION_DTE,LAST_NAME,FIRST_NAME,MIDDLE_NAME,SUFFIX,ADDR1,ADDR2,ADDR3,CITY,STATE,ZIP,PHONE,COUNTY,MEDGAS_ENDR,MRF_ENDR,WS_ENDR,INS_EXPIRY_DTE,PLUMB_COMPANY,INSURANCE_COMPANY
M,11111,Current,01/01/2020,01/01/2027,DOE,JANE,A,,1 MAIN ST,,,AUSTIN,TX,78701,5555555555,TRAVIS,No,No,No,01/01/2027,Patriot Plumbing,Carrier
M,22222,Expired,01/01/2019,01/01/2020,SMITH,JOHN,,,2 MAIN ST,,,AUSTIN,TX,78701,5555555556,TRAVIS,No,No,No,01/01/2020,Patriot Plumbing,Carrier
M,33333,Current,01/01/2020,01/01/2027,JONES,SAM,,,3 MAIN ST,,,AUSTIN,TX,78701,5555555557,TRAVIS,No,No,No,01/01/2027,Totally Different Plumbing,Carrier
M,44444,Current,01/01/2020,01/01/2027,DENSON,JEFFREY,L,,4 MAIN ST,,,AUSTIN,TX,78701,5555555558,TRAVIS,No,No,No,01/01/2027,Riot Plumbing,Carrier
"""


def test_texas_rmp_company_match_is_conservative():
    rows = texas_rmp_seeds_from_csv("Patriot Plumbing LLC", CSV)

    assert len(rows) == 1
    assert rows[0].person_name == "Jane A Doe"
    assert rows[0].role == "Responsible Master Plumber"
    assert rows[0].license_status == "current"
    assert rows[0].confidence >= 0.90


def test_texas_rmp_rejects_unrelated_company():
    rows = texas_rmp_seeds_from_csv("Rocket Plumbing", CSV)

    assert rows == []


def test_texas_tdlr_ac_company_match_returns_named_active_licensee():
    from datetime import date
    from empire_os.official_license_identity import (
        texas_tdlr_ac_seeds_from_rows,
    )

    rows = texas_tdlr_ac_seeds_from_rows(
        "Cool Air Services LLC",
        [
            {
                "license_type": "A/C Contractor",
                "business_name": "COOL AIR SERVICES INC",
                "owner_name": "SMITH, JANE A",
                "license_expiration_date_mmddccyy": "12/31/2027",
            },
            {
                "license_type": "A/C Contractor",
                "business_name": "COOL AIR SERVICES INC",
                "owner_name": "OLD, OWNER",
                "license_expiration_date_mmddccyy": "01/01/2025",
            },
        ],
        as_of=date(2026, 10, 2),
    )

    assert len(rows) == 1
    assert rows[0].person_name == "Jane A Smith"
    assert rows[0].role == "Licensed A/C Contractor"
    assert rows[0].source == "texas_tdlr_ac_contractor"
    assert rows[0].license_status == "current_by_expiration"


def test_texas_tdlr_rejects_company_name_as_owner_and_unrelated_company():
    from datetime import date
    from empire_os.official_license_identity import (
        texas_tdlr_ac_seeds_from_rows,
    )

    records = [
        {
            "license_type": "A/C Contractor",
            "business_name": "POWER SOURCE ELECTRIC",
            "owner_name": "POWER SOURCE ELECTRIC",
            "license_expiration_date_mmddccyy": "12/31/2027",
        },
        {
            "license_type": "A/C Contractor",
            "business_name": "TOTALLY DIFFERENT HVAC",
            "owner_name": "DOE, JOHN",
            "license_expiration_date_mmddccyy": "12/31/2027",
        },
    ]
    assert texas_tdlr_ac_seeds_from_rows(
        "Power Source Electric LLC",
        records,
        as_of=date(2026, 10, 2),
    ) == []


def test_find_official_license_principals_combines_cached_tdlr_and_rmp(
    monkeypatch,
):
    import empire_os.official_license_identity as module

    monkeypatch.setattr(
        module,
        "_tdlr_candidate_rows",
        lambda company_name: [{
            "license_type": "A/C Contractor",
            "business_name": "PATRIOT PLUMBING",
            "owner_name": "DOE, JANE",
            "license_expiration_date_mmddccyy": "12/31/2027",
        }],
    )
    monkeypatch.setattr(
        module,
        "_fetch_texas_rmp_csv",
        lambda timeout=12.0: CSV,
    )

    rows = module.find_official_license_principals(
        company_name="Patriot Plumbing LLC",
        state="TX",
    )

    assert {row["source"] for row in rows} == {
        "texas_tdlr_ac_contractor",
        "texas_tsbpe_rmp",
    }
    assert all(row["state"] == "TX" for row in rows)


def test_indexed_tdlr_candidate_lookup_is_bounded(tmp_path):
    import json
    import empire_os.official_license_identity as module

    records = [
        {
            "license_type": "A/C Contractor",
            "business_name": "COOL AIR SERVICES INC",
            "owner_name": "SMITH, JANE",
            "license_expiration_date_mmddccyy": "12/31/2027",
        },
        {
            "license_type": "A/C Contractor",
            "business_name": "OTHER HVAC LLC",
            "owner_name": "DOE, JOHN",
            "license_expiration_date_mmddccyy": "12/31/2027",
        },
    ]
    path = tmp_path / "cache.json"
    path.write_text(json.dumps({
        "records": records,
        "company_index": {
            "cool air services": [0],
            "other hvac": [1],
        },
        "token_index": {
            "cool": [0], "air": [0], "services": [0],
            "other": [1], "hvac": [1],
        },
    }))

    rows = module._tdlr_candidate_rows(
        "Cool Air Services LLC",
        cache_path=path,
    )
    assert len(rows) == 1
    assert rows[0]["owner_name"] == "SMITH, JANE"
