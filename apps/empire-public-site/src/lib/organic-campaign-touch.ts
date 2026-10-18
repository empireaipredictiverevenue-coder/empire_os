/** Strict, nonidentifying URL token handoff. No cookie or browser storage. */
export type OrganicTouch = {
  campaign_id: string;
  asset_id: string;
  source: string;
  medium: string;
  landing_path: string;
};

const sources: Record<string, [string, string]> = {
  linkedin: ["organic_social", "linkedin"],
  youtube: ["organic_video", "youtube"],
  owned_newsletter: ["email", "newsletter"],
};

const pages = new Set(["/industries/solar", "/industries/roofing", "/commercial"]);
const pattern = /^campaign_[a-f0-9]{24}$/;

/** A claimed link token, NOT evidence of a recorded session or publication. */
export function organicTouchFromSearch(search: string, landingPath: string): OrganicTouch | null {
  if (!pages.has(landingPath) || search.length > 1600) return null;
  const query = new URLSearchParams(search);
  for (const name of ["utm_campaign", "utm_content", "utm_source", "utm_medium"]) {
    if (query.getAll(name).length !== 1) return null;
  }
  const campaign_id = query.get("utm_campaign") || "";
  const asset_id = query.get("utm_content") || "";
  const source = query.get("utm_source") || "";
  const medium = query.get("utm_medium") || "";
  const pair = sources[source];
  if (!pattern.test(campaign_id) || !pair || medium !== pair[0] ||
      asset_id !== campaign_id + ":" + pair[1]) return null;
  return { campaign_id, asset_id, source, medium, landing_path: landingPath };
}

/** Called only when the visitor clicks an existing owned-page commercial CTA. */
export function linkedCommercialHref(search: string, currentPath: string): string {
  if (currentPath !== "/industries/solar" && currentPath !== "/industries/roofing")
    return "/commercial";
  const touch = organicTouchFromSearch(search, currentPath);
  if (!touch) return "/commercial";
  const params = new URLSearchParams({
    utm_campaign: touch.campaign_id, utm_content: touch.asset_id,
    utm_source: touch.source, utm_medium: touch.medium,
    utm_landing: touch.landing_path,
  });
  return "/commercial?" + params.toString();
}

/** Exact one-hop receipt at /commercial; no cross-session identity is created. */
export function commercialTouchFromSearch(search: string): OrganicTouch | null {
  if (search.length > 1600) return null;
  const params = new URLSearchParams(search);
  if (params.getAll("utm_landing").length !== 1) return null;
  const landingPath = params.get("utm_landing") || "";
  return organicTouchFromSearch(search, landingPath);
}
