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
