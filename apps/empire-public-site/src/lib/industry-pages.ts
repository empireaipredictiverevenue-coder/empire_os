export type IndustryPage = {
  slug: string;
  eyebrow: string;
  title: string;
  subtitle: string;
  summary: string;
  signals: string[];
  questions: string[];
  products: string[];
  forecast: string[];
  links: { label: string; href: string }[];
};

export const industryPages: IndustryPage[] = [
  {
    slug: "solar",
    eyebrow: "SOLAR & ENERGY INTELLIGENCE",
    title: "See solar opportunity before it becomes obvious.",
    subtitle: "Market signals, property triggers and commercial intelligence for solar growth.",
    summary:
      "Empire connects installer coverage, permitting, property signals, weather events, market demand and commercial evidence into one decision layer. The goal is not another lead list. It is to show where demand is forming, why it matters and what evidence supports action.",
    signals: [
      "Installer and territory coverage",
      "Permit and project activity",
      "Property suitability signals",
      "Weather and replacement triggers",
      "Commercial expansion signals",
      "Search and buyer-intent movement",
    ],
    questions: [
      "Where is solar demand strengthening?",
      "Which territories are under-served?",
      "What property or permit signals precede opportunity?",
      "Which installers appear to have capacity to grow?",
      "What changes over the next 6–24 months could reshape demand?",
    ],
    products: [
      "Solar territory intelligence",
      "Property solar opportunity maps",
      "Installer intelligence",
      "Permit-trigger alerts",
      "Commercial solar opportunity feeds",
    ],
    forecast: [
      "30/90-day operational demand",
      "6/12/18/24-month market direction",
      "Trend acceleration and structural breaks",
      "Channel, pricing and competitive change",
    ],
    links: [
      { label: "HVAC intelligence", href: "/industries/hvac" },
      { label: "Property intelligence", href: "/industries/property" },
    ],
  },
  {
    slug: "hvac",
    eyebrow: "HVAC & CLIMATE SERVICES INTELLIGENCE",
    title: "Understand where HVAC demand is building next.",
    subtitle: "Weather, property, replacement-cycle and contractor intelligence in one market view.",
    summary:
      "Empire joins weather stress, contractor coverage, permit activity, property signals, search demand and buyer readiness so operators can see where service, replacement and upgrade demand is moving.",
    signals: [
      "Weather-load and climate stress",
      "Replacement and upgrade signals",
      "Contractor territory coverage",
      "Permit and property activity",
      "Search demand and intent",
      "Capacity and expansion signals",
    ],
    questions: [
      "Where are replacement cycles likely to accelerate?",
      "Which territories have demand but limited contractor coverage?",
      "How are heat, cooling and electrification trends changing the market?",
      "Which companies appear positioned to expand?",
      "What does the next 6–24 months look like by market regime?",
    ],
    products: [
      "HVAC contractor intelligence",
      "Weather-load alerts",
      "Replacement-demand signals",
      "Territory intelligence",
      "Building-upgrade opportunity feeds",
    ],
    forecast: [
      "30/90-day demand pressure",
      "6/12/18/24-month market direction",
      "Seasonality and regime shifts",
      "Technology and channel change",
    ],
    links: [
      { label: "Solar intelligence", href: "/industries/solar" },
      { label: "Roofing intelligence", href: "/industries/roofing" },
    ],
  },
  {
    slug: "legal-mass-tort",
    eyebrow: "LEGAL & MASS TORT INTELLIGENCE",
    title: "Map legal demand, firm capacity and mass-tort movement.",
    subtitle: "A market-intelligence layer for plaintiff firms, campaigns and emerging legal opportunity.",
    summary:
      "Empire combines law-firm identity, public court data, search demand, campaign signals, public registries and market-change evidence to build a more complete view of where legal demand and firm capacity are moving.",
    signals: [
      "Law-firm and decision-maker identity",
      "Court and docket activity",
      "Mass-tort topic movement",
      "Search and content demand",
      "Competitive campaign signals",
      "Firm capacity and expansion evidence",
    ],
    questions: [
      "Which mass-tort topics are gaining commercial attention?",
      "Which firms appear active or expanding?",
      "Where are competitor campaigns intensifying?",
      "Which legal markets show emerging demand gaps?",
      "How could intake and acquisition models change over the next 6–24 months?",
    ],
    products: [
      "Law-firm market maps",
      "Firm-buyer intelligence",
      "Case-demand signals",
      "Competitor campaign intelligence",
      "Mass-tort opportunity feeds",
    ],
    forecast: [
      "Near-term demand movement",
      "6/12/18/24-month legal market scenarios",
      "Campaign-intensity change",
      "Firm acquisition-model change",
    ],
    links: [
      { label: "Property intelligence", href: "/industries/property" },
      { label: "Trust Center", href: "/trust" },
    ],
  },
  {
    slug: "roofing",
    eyebrow: "ROOFING & RESTORATION INTELLIGENCE",
    title: "Turn storm, property and market signals into roofing intelligence.",
    subtitle: "Territory, contractor, storm and project signals designed around commercial decisions.",
    summary:
      "Empire connects weather events, property evidence, permits, contractor coverage, search demand and verified business signals to identify where roofing and restoration opportunity may be forming.",
    signals: [
      "Storm and weather events",
      "Property and permit activity",
      "Contractor territory coverage",
      "Restoration demand signals",
      "Search and buyer intent",
      "Capacity and expansion evidence",
    ],
    questions: [
      "Which markets are moving after severe weather?",
      "Where is contractor capacity tight?",
      "Which property signals indicate likely repair demand?",
      "Where are search and buyer signals rising together?",
      "How could restoration economics change over the next 6–24 months?",
    ],
    products: [
      "Roofing territory intelligence",
      "Storm-trigger alerts",
      "Contractor market maps",
      "Property opportunity feeds",
      "Restoration demand intelligence",
    ],
    forecast: [
      "30/90-day storm-linked demand",
      "6/12/18/24-month market direction",
      "Capacity and pricing pressure",
      "Competitive and channel change",
    ],
    links: [
      { label: "Property intelligence", href: "/industries/property" },
      { label: "HVAC intelligence", href: "/industries/hvac" },
    ],
  },
  {
    slug: "property",
    eyebrow: "PROPERTY OPPORTUNITY INTELLIGENCE",
    title: "Build an evidence graph around every property opportunity.",
    subtitle: "Permits, violations, weather, ownership and service-demand signals connected over time.",
    summary:
      "Empire treats property as an intelligence graph rather than a static record. Signals can accumulate across permits, violations, weather, ownership, local demand and commercial activity so opportunities are ranked from evidence instead of guesswork.",
    signals: [
      "Permit and renovation activity",
      "Violation and distress signals",
      "Weather and damage triggers",
      "Ownership and operator evidence",
      "Local service demand",
      "Linked contractor capacity",
    ],
    questions: [
      "Which properties show multiple independent opportunity signals?",
      "Where are renovation and repair triggers clustering?",
      "How are weather events changing local service demand?",
      "Which owners or operators may need commercial services?",
      "What market changes could alter property opportunity over 6–24 months?",
    ],
    products: [
      "Property opportunity graphs",
      "Distress and renovation alerts",
      "Owner intelligence",
      "Territory demand maps",
      "Service-opportunity feeds",
    ],
    forecast: [
      "30/90-day trigger movement",
      "6/12/18/24-month territory direction",
      "Property-service regime change",
      "Demand/capacity imbalance",
    ],
    links: [
      { label: "Roofing intelligence", href: "/industries/roofing" },
      { label: "Private capital intelligence", href: "/industries/private-equity" },
    ],
  },
  {
    slug: "private-equity",
    eyebrow: "PRIVATE CAPITAL & ROLL-UP INTELLIGENCE",
    title: "Find the next platform, add-on and roll-up opportunity earlier.",
    subtitle:
      "Sponsor, portfolio, fragmentation and owner-exit intelligence across property and service markets.",
    summary:
      "Empire connects public adviser data, sponsor portfolios, acquisition announcements, company registries, property and operating signals, search demand and market structure into a private-capital intelligence graph. The objective is to identify where consolidation is accelerating, which businesses fit an add-on thesis, and where portfolio companies can grow next.",
    signals: [
      "Sponsor and portfolio-company mapping",
      "Fragmentation and consolidation intensity",
      "Platform and add-on acquisition signals",
      "Founder and owner-exit indicators",
      "Portfolio-company growth opportunities",
      "Property, demand and market-regime signals",
    ],
    questions: [
      "Which fragmented markets are moving into a consolidation window?",
      "Which companies fit an existing sponsor-backed platform as an add-on?",
      "Where are owner-exit or succession signals becoming visible?",
      "Which portfolio companies have adjacent territory or cross-sell opportunities?",
      "How could financing, pricing and market structure change over the next 6–24 months?",
    ],
    products: [
      "Private-equity sponsor graph",
      "Roll-up market maps",
      "Add-on target feeds",
      "Founder-exit signal feeds",
      "Portfolio growth opportunity maps",
      "Consolidation indices",
    ],
    forecast: [
      "30/90-day deal and market movement",
      "6/12/18/24-month consolidation regimes",
      "Platform/add-on opportunity windows",
      "Portfolio growth and exit-environment change",
    ],
    links: [
      { label: "Property intelligence", href: "/industries/property" },
      { label: "HVAC intelligence", href: "/industries/hvac" },
      { label: "Solar intelligence", href: "/industries/solar" },
    ],
  },
];

export function getIndustryPage(slug: string) {
  return industryPages.find((page) => page.slug === slug);
}
