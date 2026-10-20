// Hand-curated, contextual internal links between already-published pages.
// This is not a bulk linking engine, purchased backlink scheme or proof of results.
// The site owner verifies each destination at release. Never infer SEO uplift.
export type EditorialLink = {
  href: string;
  label: string;
  context: string;
};

export const industryEditorialLinks: Record<string, readonly EditorialLink[]> = {
  roofing: [
    {
      href: "/aeo/roofing/DFW/",
      label: "Dallas–Fort Worth roofing market questions",
      context: "Review the local market research framework before deciding which coverage or contractor signals are relevant.",
    },
    {
      href: "/research/campaign_3438b6c3b110f941407ce1dd",
      label: "Denver roofing coverage-gap research method",
      context: "See how a roofing coverage question can be scoped from public evidence, without treating research as a verified sale.",
    },
  ],
  solar: [
    {
      href: "/industries/roofing",
      label: "Roofing and property-condition intelligence",
      context: "Examine roof and property signals that may affect the suitability or timing of solar installations.",
    },
    {
      href: "/predictive-revenue",
      label: "Predictive Revenue for complex sales decisions",
      context: "Understand how commercial forecasts should remain distinct from confirmed installer enquiries or revenue.",
    },
  ],
  hvac: [
    {
      href: "/aeo/hvac/DFW/",
      label: "Dallas–Fort Worth HVAC market questions",
      context: "Explore how territory, replacement cycles and weather can shape an HVAC research question.",
    },
    {
      href: "/research/campaign_99a64a18052abf58600b64a6",
      label: "Dallas–Fort Worth HVAC opportunity research",
      context: "Follow an evidence-bound example of how to frame an HVAC territory-intelligence assessment.",
    },
    {
      href: "/research/campaign_83ccabdbe7356a6f17d77440",
      label: "Denver HVAC evidence-to-question framework",
      context: "Compare a second market research method without implying a verified customer outcome.",
    },
    {
      href: "/industries/property",
      label: "Property and building-upgrade signals",
      context: "Understand the property evidence behind replacement and building-service decisions.",
    },
  ],
  "legal-mass-tort": [
    {
      href: "/research/campaign_948947123543615f2c6eab7f",
      label: "Atlanta class-action research methodology",
      context: "Review a case-demand research framework, not an assertion that any claim or client has been secured.",
    },
    {
      href: "/predictive-revenue",
      label: "Evidence-bound revenue forecasting",
      context: "See how forecasts, firm activity and realised commercial outcomes should be kept separate.",
    },
  ],
  property: [
    {
      href: "/aeo/general_contractor/NYC/",
      label: "New York general-contractor market questions",
      context: "Explore which local contractor and property signals may deserve further verification.",
    },
    {
      href: "/research/campaign_7d5e758b1ec56415de7516a6",
      label: "New York contractor research evidence chain",
      context: "Examine a research-scoping example while treating projected opportunities as unverified.",
    },
    {
      href: "/industries/hvac",
      label: "Heating and cooling upgrade signals",
      context: "Connect building conditions and replacement cycles with relevant HVAC commercial questions.",
    },
    {
      href: "/industries/solar",
      label: "Solar suitability and permit signals",
      context: "Consider property suitability, permits and installer coverage in the solar market context.",
    },
  ],
  "private-equity": [
    {
      href: "/industries/roofing",
      label: "Roofing contractor market intelligence",
      context: "Examine one property-services market when researching potential operating or growth theses.",
    },
    {
      href: "/predictive-revenue",
      label: "Forecasting versus realised revenue",
      context: "See the distinction between directional scenarios and verified commercial outcomes in a portfolio.",
    },
  ],
};
