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

INTERNATIONAL_MARKETS = (
    _market("GB-LON","GB","England","London",51.5074,-0.1278,"Europe/London","en-GB",1.20),
    _market("GB-MAN","GB","England","Manchester",53.4808,-2.2426,"Europe/London","en-GB",1.10),
    _market("GB-BHM","GB","England","Birmingham",52.4862,-1.8904,"Europe/London","en-GB",1.05),
    _market("GB-GLA","GB","Scotland","Glasgow",55.8642,-4.2518,"Europe/London","en-GB",1.00),
    _market("GB-EDI","GB","Scotland","Edinburgh",55.9533,-3.1883,"Europe/London","en-GB",1.00),
    _market("GB-CDF","GB","Wales","Cardiff",51.4816,-3.1791,"Europe/London","en-GB",1.00),
    _market("GB-BFS","GB","Northern Ireland","Belfast",54.5973,-5.9301,"Europe/London","en-GB",0.95),
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
)

MARKETS = US_MARKETS + US_SECONDARY_MARKETS + INTERNATIONAL_MARKETS


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
