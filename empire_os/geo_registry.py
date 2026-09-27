"""Canonical acquisition geography registry for EmpireOS.

Markets are explicit commercial crawl anchors. Locale facts are evidence, not
guesses: every market carries country, region, timezone and acquisition
language so downstream scoring/outreach can remain country-aware.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from empire_os.locale_intelligence import resolve_locale


@dataclass(frozen=True)
class GeoMarket:
    market_id: str
    country_code: str
    region_code: str
    metro: str
    latitude: float
    longitude: float
    timezone: str
    language_code: str
    base_priority: float = 1.0
    enabled: bool = True

    def as_dict(self) -> dict:
        value = asdict(self)
        value["locale"] = resolve_locale({
            "country_code": self.country_code,
            "state": self.region_code,
            "metro": self.metro,
            "timezone": self.timezone,
            "source_language": self.language_code,
        }).as_dict()
        return value


def _market(
    market_id: str,
    country: str,
    region: str,
    metro: str,
    lat: float,
    lon: float,
    tz: str,
    language: str,
    priority: float = 1.0,
) -> GeoMarket:
    return GeoMarket(
        market_id=market_id,
        country_code=country,
        region_code=region,
        metro=metro,
        latitude=lat,
        longitude=lon,
        timezone=tz,
        language_code=language,
        base_priority=priority,
    )


# One commercial anchor in every US state plus DC.
_US = (
    ("US-AL","AL","Birmingham, AL",33.518589,-86.810357,"America/Chicago"),
    ("US-AK","AK","Anchorage, AK",61.218056,-149.900278,"America/Anchorage"),
    ("US-AZ","AZ","Phoenix, AZ",33.448376,-112.074036,"America/Phoenix"),
    ("US-AR","AR","Little Rock, AR",34.746481,-92.289595,"America/Chicago"),
    ("US-CA","CA","Los Angeles, CA",34.052235,-118.243683,"America/Los_Angeles"),
    ("US-CO","CO","Denver, CO",39.739235,-104.990250,"America/Denver"),
    ("US-CT","CT","Hartford, CT",41.765804,-72.673372,"America/New_York"),
    ("US-DE","DE","Wilmington, DE",39.739072,-75.539788,"America/New_York"),
    ("US-FL","FL","Miami, FL",25.761680,-80.191790,"America/New_York"),
    ("US-GA","GA","Atlanta, GA",33.749001,-84.387978,"America/New_York"),
    ("US-HI","HI","Honolulu, HI",21.306944,-157.858337,"Pacific/Honolulu"),
    ("US-ID","ID","Boise, ID",43.615021,-116.202314,"America/Boise"),
    ("US-IL","IL","Chicago, IL",41.878113,-87.629799,"America/Chicago"),
    ("US-IN","IN","Indianapolis, IN",39.768403,-86.158068,"America/Indiana/Indianapolis"),
    ("US-IA","IA","Des Moines, IA",41.586835,-93.624959,"America/Chicago"),
    ("US-KS","KS","Wichita, KS",37.687176,-97.330053,"America/Chicago"),
    ("US-KY","KY","Louisville, KY",38.252665,-85.758456,"America/Kentucky/Louisville"),
    ("US-LA","LA","New Orleans, LA",29.951066,-90.071532,"America/Chicago"),
    ("US-ME","ME","Portland, ME",43.659099,-70.256819,"America/New_York"),
    ("US-MD","MD","Baltimore, MD",39.290386,-76.612190,"America/New_York"),
    ("US-MA","MA","Boston, MA",42.360081,-71.058884,"America/New_York"),
    ("US-MI","MI","Detroit, MI",42.331429,-83.045753,"America/Detroit"),
    ("US-MN","MN","Minneapolis, MN",44.977753,-93.265011,"America/Chicago"),
    ("US-MS","MS","Jackson, MS",32.298757,-90.184810,"America/Chicago"),
    ("US-MO","MO","Kansas City, MO",39.099727,-94.578567,"America/Chicago"),
    ("US-MT","MT","Billings, MT",45.783286,-108.500690,"America/Denver"),
    ("US-NE","NE","Omaha, NE",41.256538,-95.934502,"America/Chicago"),
    ("US-NV","NV","Las Vegas, NV",36.169941,-115.139830,"America/Los_Angeles"),
    ("US-NH","NH","Manchester, NH",42.995640,-71.454789,"America/New_York"),
    ("US-NJ","NJ","Newark, NJ",40.735657,-74.172363,"America/New_York"),
    ("US-NM","NM","Albuquerque, NM",35.084385,-106.650421,"America/Denver"),
    ("US-NY","NY","New York, NY",40.712776,-74.005974,"America/New_York"),
    ("US-NC","NC","Charlotte, NC",35.227087,-80.843127,"America/New_York"),
    ("US-ND","ND","Fargo, ND",46.877186,-96.789803,"America/Chicago"),
    ("US-OH","OH","Columbus, OH",39.961176,-82.998794,"America/New_York"),
    ("US-OK","OK","Oklahoma City, OK",35.467560,-97.516428,"America/Chicago"),
    ("US-OR","OR","Portland, OR",45.515232,-122.678385,"America/Los_Angeles"),
    ("US-PA","PA","Philadelphia, PA",39.952583,-75.165222,"America/New_York"),
    ("US-RI","RI","Providence, RI",41.824000,-71.412800,"America/New_York"),
    ("US-SC","SC","Charleston, SC",32.776475,-79.931051,"America/New_York"),
    ("US-SD","SD","Sioux Falls, SD",43.544596,-96.731103,"America/Chicago"),
    ("US-TN","TN","Nashville, TN",36.162664,-86.781602,"America/Chicago"),
    ("US-TX","TX","Dallas, TX",32.776672,-96.796988,"America/Chicago"),
    ("US-UT","UT","Salt Lake City, UT",40.760780,-111.891045,"America/Denver"),
    ("US-VT","VT","Burlington, VT",44.475883,-73.212072,"America/New_York"),
    ("US-VA","VA","Richmond, VA",37.540725,-77.436048,"America/New_York"),
    ("US-WA","WA","Seattle, WA",47.606209,-122.332069,"America/Los_Angeles"),
    ("US-WV","WV","Charleston, WV",38.349820,-81.632623,"America/New_York"),
    ("US-WI","WI","Milwaukee, WI",43.038902,-87.906474,"America/Chicago"),
    ("US-WY","WY","Cheyenne, WY",41.139981,-104.820246,"America/Denver"),
    ("US-DC","DC","Washington, DC",38.907192,-77.036873,"America/New_York"),
)

US_MARKETS = tuple(
    _market(mid, "US", region, metro, lat, lon, tz, "en-US", 1.15)
    for mid, region, metro, lat, lon, tz in _US
)

# Preserve high-value metros already proven by the acquisition soak.
US_SECONDARY_MARKETS = (
    _market("US-TX-HOU","US","TX","Houston, TX",29.763284,-95.363271,"America/Chicago","en-US",1.30),
    _market("US-TX-AUS","US","TX","Austin, TX",30.267153,-97.743057,"America/Chicago","en-US",1.25),
    _market("US-TX-SAT","US","TX","San Antonio, TX",29.424122,-98.493628,"America/Chicago","en-US",1.20),
    _market("US-FL-TPA","US","FL","Tampa, FL",27.950575,-82.457177,"America/New_York","en-US",1.20),
    _market("US-FL-ORL","US","FL","Orlando, FL",28.538336,-81.379234,"America/New_York","en-US",1.15),
    _market("US-FL-JAX","US","FL","Jacksonville, FL",30.332184,-81.655651,"America/New_York","en-US",1.10),
    _market("US-CA-SD","US","CA","San Diego, CA",32.715736,-117.161087,"America/Los_Angeles","en-US",1.15),
    _market("US-CA-SAC","US","CA","Sacramento, CA",38.581572,-121.494400,"America/Los_Angeles","en-US",1.10),
    _market("US-CA-SJ","US","CA","San Jose, CA",37.338207,-121.886330,"America/Los_Angeles","en-US",1.20),
    _market("US-CA-FRE","US","CA","Fresno, CA",36.737797,-119.787125,"America/Los_Angeles","en-US",1.00),
    _market("US-NC-RDU","US","NC","Raleigh, NC",35.779591,-78.638176,"America/New_York","en-US",1.10),
    _market("US-TN-MEM","US","TN","Memphis, TN",35.149532,-90.048981,"America/Chicago","en-US",1.00),
    _market("US-PA-PIT","US","PA","Pittsburgh, PA",40.440625,-79.995886,"America/New_York","en-US",1.05),
    _market("US-OH-CIN","US","OH","Cincinnati, OH",39.103119,-84.512016,"America/New_York","en-US",1.05),
    _market("US-OH-CLE","US","OH","Cleveland, OH",41.499320,-81.694361,"America/New_York","en-US",1.05),
    _market("US-OK-TUL","US","OK","Tulsa, OK",36.153982,-95.992775,"America/Chicago","en-US",1.00),
    _market("US-MO-STL","US","MO","St. Louis, MO",38.627003,-90.199404,"America/Chicago","en-US",1.05),
    _market("US-VA-VB","US","VA","Virginia Beach, VA",36.852926,-75.977985,"America/New_York","en-US",1.00),
    _market("US-AZ-TUS","US","AZ","Tucson, AZ",32.222607,-110.974711,"America/Phoenix","en-US",1.00),
)

UK_MARKETS = (
    # England
    _market("GB-LON","GB","England","London",51.5074,-0.1278,"Europe/London","en-GB",1.30),
    _market("GB-MAN","GB","England","Manchester",53.4808,-2.2426,"Europe/London","en-GB",1.20),
    _market("GB-BHM","GB","England","Birmingham",52.4862,-1.8904,"Europe/London","en-GB",1.20),
    _market("GB-LIV","GB","England","Liverpool",53.4084,-2.9916,"Europe/London","en-GB",1.10),
    _market("GB-LDS","GB","England","Leeds",53.8008,-1.5491,"Europe/London","en-GB",1.10),
    _market("GB-SHF","GB","England","Sheffield",53.3811,-1.4701,"Europe/London","en-GB",1.05),
    _market("GB-NCL","GB","England","Newcastle upon Tyne",54.9783,-1.6178,"Europe/London","en-GB",1.05),
    _market("GB-BRS","GB","England","Bristol",51.4545,-2.5879,"Europe/London","en-GB",1.10),
    _market("GB-NOT","GB","England","Nottingham",52.9548,-1.1581,"Europe/London","en-GB",1.00),
    _market("GB-LEI","GB","England","Leicester",52.6369,-1.1398,"Europe/London","en-GB",1.00),
    _market("GB-COV","GB","England","Coventry",52.4068,-1.5197,"Europe/London","en-GB",1.00),
    _market("GB-SOU","GB","England","Southampton",50.9097,-1.4044,"Europe/London","en-GB",1.00),
    _market("GB-POR","GB","England","Portsmouth",50.8198,-1.0880,"Europe/London","en-GB",0.95),
    _market("GB-BTN","GB","England","Brighton",50.8225,-0.1372,"Europe/London","en-GB",1.00),
    _market("GB-RDG","GB","England","Reading",51.4543,-0.9781,"Europe/London","en-GB",1.00),
    _market("GB-OXF","GB","England","Oxford",51.7520,-1.2577,"Europe/London","en-GB",0.95),
    _market("GB-CAM","GB","England","Cambridge",52.2053,0.1218,"Europe/London","en-GB",0.95),
    _market("GB-MKD","GB","England","Milton Keynes",52.0406,-0.7594,"Europe/London","en-GB",1.00),
    _market("GB-NRW","GB","England","Norwich",52.6309,1.2974,"Europe/London","en-GB",0.95),
    _market("GB-PLY","GB","England","Plymouth",50.3755,-4.1427,"Europe/London","en-GB",0.95),
    _market("GB-EXE","GB","England","Exeter",50.7184,-3.5339,"Europe/London","en-GB",0.90),
    _market("GB-BOH","GB","England","Bournemouth",50.7192,-1.8808,"Europe/London","en-GB",0.95),
    _market("GB-YRK","GB","England","York",53.9590,-1.0815,"Europe/London","en-GB",0.90),
    _market("GB-HUL","GB","England","Hull",53.7676,-0.3274,"Europe/London","en-GB",0.90),
    _market("GB-STK","GB","England","Stoke-on-Trent",53.0027,-2.1794,"Europe/London","en-GB",0.90),
    _market("GB-DRB","GB","England","Derby",52.9225,-1.4746,"Europe/London","en-GB",0.90),
    _market("GB-WLV","GB","England","Wolverhampton",52.5862,-2.1287,"Europe/London","en-GB",0.90),
    _market("GB-SUN","GB","England","Sunderland",54.9069,-1.3838,"Europe/London","en-GB",0.90),
    _market("GB-MDB","GB","England","Middlesbrough",54.5742,-1.2350,"Europe/London","en-GB",0.90),
    _market("GB-BPL","GB","England","Blackpool",53.8175,-3.0357,"Europe/London","en-GB",0.85),
    _market("GB-BOL","GB","England","Bolton",53.5769,-2.4282,"Europe/London","en-GB",1.00),

    # Scotland
    _market("GB-GLA","GB","Scotland","Glasgow",55.8642,-4.2518,"Europe/London","en-GB",1.10),
    _market("GB-EDI","GB","Scotland","Edinburgh",55.9533,-3.1883,"Europe/London","en-GB",1.10),
    _market("GB-ABD","GB","Scotland","Aberdeen",57.1497,-2.0943,"Europe/London","en-GB",0.95),
    _market("GB-DND","GB","Scotland","Dundee",56.4620,-2.9707,"Europe/London","en-GB",0.90),
    _market("GB-INV","GB","Scotland","Inverness",57.4778,-4.2247,"Europe/London","en-GB",0.85),
    _market("GB-STG","GB","Scotland","Stirling",56.1165,-3.9369,"Europe/London","en-GB",0.85),

    # Wales
    _market("GB-CDF","GB","Wales","Cardiff",51.4816,-3.1791,"Europe/London","en-GB",1.05),
    _market("GB-SWA","GB","Wales","Swansea",51.6214,-3.9436,"Europe/London","en-GB",0.95),
    _market("GB-NWP","GB","Wales","Newport",51.5842,-2.9977,"Europe/London","en-GB",0.90),
    _market("GB-WRX","GB","Wales","Wrexham",53.0465,-2.9938,"Europe/London","en-GB",0.85),

    # Northern Ireland
    _market("GB-BFS","GB","Northern Ireland","Belfast",54.5973,-5.9301,"Europe/London","en-GB",1.00),
    _market("GB-DRY","GB","Northern Ireland","Derry",54.9966,-7.3086,"Europe/London","en-GB",0.85),
    _market("GB-LSB","GB","Northern Ireland","Lisburn",54.5162,-6.0580,"Europe/London","en-GB",0.80),
    _market("GB-NRY","GB","Northern Ireland","Newry",54.1751,-6.3402,"Europe/London","en-GB",0.80),
)

INTERNATIONAL_MARKETS = (
    _market("CA-TOR","CA","ON","Toronto, ON",43.6532,-79.3832,"America/Toronto","en-CA",1.15),
    _market("CA-VAN","CA","BC","Vancouver, BC",49.2827,-123.1207,"America/Vancouver","en-CA",1.10),
    _market("CA-MTL","CA","QC","Montreal, QC",45.5017,-73.5673,"America/Toronto","fr-CA",1.05),
    _market("CA-CGY","CA","AB","Calgary, AB",51.0447,-114.0719,"America/Edmonton","en-CA",1.05),
    _market("CA-EDM","CA","AB","Edmonton, AB",53.5461,-113.4938,"America/Edmonton","en-CA",1.00),
    _market("CA-OTT","CA","ON","Ottawa, ON",45.4215,-75.6972,"America/Toronto","en-CA",1.00),
    _market("AU-SYD","AU","NSW","Sydney, NSW",-33.8688,151.2093,"Australia/Sydney","en-AU",1.15),
    _market("AU-MEL","AU","VIC","Melbourne, VIC",-37.8136,144.9631,"Australia/Melbourne","en-AU",1.10),
    _market("AU-BNE","AU","QLD","Brisbane, QLD",-27.4698,153.0251,"Australia/Brisbane","en-AU",1.05),
    _market("AU-PER","AU","WA","Perth, WA",-31.9505,115.8605,"Australia/Perth","en-AU",1.00),
    _market("AU-ADL","AU","SA","Adelaide, SA",-34.9285,138.6007,"Australia/Adelaide","en-AU",0.95),
    _market("IE-DUB","IE","Leinster","Dublin",53.3498,-6.2603,"Europe/Dublin","en-IE",1.05),
    _market("IE-ORK","IE","Munster","Cork",51.8985,-8.4756,"Europe/Dublin","en-IE",0.90),
    _market("NZ-AKL","NZ","Auckland","Auckland",-36.8485,174.7633,"Pacific/Auckland","en-NZ",1.00),
    _market("NZ-WLG","NZ","Wellington","Wellington",-41.2866,174.7756,"Pacific/Auckland","en-NZ",0.90),
    _market("DE-BER","DE","BE","Berlin",52.5200,13.4050,"Europe/Berlin","de-DE",1.10),
    _market("DE-MUC","DE","BY","Munich",48.1351,11.5820,"Europe/Berlin","de-DE",1.05),
    _market("DE-HAM","DE","HH","Hamburg",53.5511,9.9937,"Europe/Berlin","de-DE",1.00),
    _market("FR-PAR","FR","IDF","Paris",48.8566,2.3522,"Europe/Paris","fr-FR",1.10),
    _market("FR-LYO","FR","ARA","Lyon",45.7640,4.8357,"Europe/Paris","fr-FR",1.00),
    _market("FR-MRS","FR","PAC","Marseille",43.2965,5.3698,"Europe/Paris","fr-FR",0.95),
    _market("ES-MAD","ES","MD","Madrid",40.4168,-3.7038,"Europe/Madrid","es-ES",1.10),
    _market("ES-BCN","ES","CT","Barcelona",41.3874,2.1686,"Europe/Madrid","es-ES",1.05),
    _market("ES-VAL","ES","VC","Valencia",39.4699,-0.3763,"Europe/Madrid","es-ES",0.95),
    _market("IT-MIL","IT","LOM","Milan",45.4642,9.1900,"Europe/Rome","it-IT",1.05),
    _market("IT-ROM","IT","LAZ","Rome",41.9028,12.4964,"Europe/Rome","it-IT",1.00),
    _market("IT-NAP","IT","CAM","Naples",40.8518,14.2681,"Europe/Rome","it-IT",0.90),
    _market("NL-AMS","NL","NH","Amsterdam",52.3676,4.9041,"Europe/Amsterdam","nl-NL",1.05),
    _market("NL-RTM","NL","ZH","Rotterdam",51.9244,4.4777,"Europe/Amsterdam","nl-NL",1.00),
    _market("BE-BRU","BE","BRU","Brussels",50.8503,4.3517,"Europe/Brussels","",1.00),
    _market("BE-ANR","BE","VLG","Antwerp",51.2194,4.4025,"Europe/Brussels","nl-BE",0.95),
    _market("PT-LIS","PT","LIS","Lisbon",38.7223,-9.1393,"Europe/Lisbon","pt-PT",1.00),
    _market("PT-OPO","PT","POR","Porto",41.1579,-8.6291,"Europe/Lisbon","pt-PT",0.95),
)

MARKETS = US_MARKETS + US_SECONDARY_MARKETS + UK_MARKETS + INTERNATIONAL_MARKETS


def acquisition_markets(*, countries: Iterable[str] | None = None) -> tuple[GeoMarket, ...]:
    allowed = {str(x).upper() for x in countries} if countries else None
    return tuple(
        market for market in MARKETS
        if market.enabled and (allowed is None or market.country_code in allowed)
    )


def market_coordinates() -> dict[str, tuple[float, float]]:
    return {
        market.metro: (market.latitude, market.longitude)
        for market in acquisition_markets()
    }


def market_by_metro(metro: str) -> GeoMarket | None:
    needle = str(metro or "").strip().casefold()
    return next(
        (market for market in acquisition_markets()
         if market.metro.casefold() == needle),
        None,
    )


LEGACY_US_METROS = (
    "Houston, TX", "Dallas, TX", "Austin, TX", "San Antonio, TX",
    "Phoenix, AZ", "Chicago, IL", "Atlanta, GA", "Miami, FL",
    "Denver, CO", "Los Angeles, CA", "New York, NY", "Seattle, WA",
    "Charlotte, NC", "Nashville, TN", "Tampa, FL", "Philadelphia, PA",
    "Washington, DC", "Boston, MA", "Detroit, MI", "Minneapolis, MN",
    "Portland, OR", "Las Vegas, NV", "Orlando, FL", "Jacksonville, FL",
    "Raleigh, NC", "Columbus, OH", "Indianapolis, IN", "Kansas City, MO",
    "St. Louis, MO", "Pittsburgh, PA", "Baltimore, MD", "Cincinnati, OH",
    "Cleveland, OH", "Salt Lake City, UT", "San Diego, CA",
    "Sacramento, CA", "San Jose, CA", "Oklahoma City, OK", "Tulsa, OK",
    "New Orleans, LA", "Birmingham, AL", "Richmond, VA",
    "Virginia Beach, VA", "Milwaukee, WI", "Louisville, KY",
    "Memphis, TN", "Albuquerque, NM", "Tucson, AZ", "Fresno, CA",
    "Omaha, NE",
)


def legacy_us_markets() -> tuple[GeoMarket, ...]:
    rows = []
    for metro in LEGACY_US_METROS:
        market = market_by_metro(metro)
        if market is None:
            raise RuntimeError(f"legacy US market missing from registry: {metro}")
        rows.append(market)
    return tuple(rows)
