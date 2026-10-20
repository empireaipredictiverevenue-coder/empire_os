/** Browser-claimed *navigation context* for existing EmpireDB commercial intake.

Not proof of a visit, SEO search click, campaign touch, person, intent,
consent or revenue. Never accept UTM strings, user-supplied query values,
external referrers, arbitrary paths or contact identifiers.
*/
export const REVIEWED_ENTRY_PAGES = Object.freeze([
  "/", "/commercial", "/predictive-revenue",
  "/industries/roofing", "/industries/solar", "/industries/hvac",
  "/industries/property", "/insights/revenue-opportunity-assessment",
] as const);

export function reviewedCommercialEntryPage(
  referrer: unknown,
  currentOrigin: unknown,
): (typeof REVIEWED_ENTRY_PAGES)[number] {
  if(typeof referrer!=="string" || !referrer || typeof currentOrigin!=="string")
    return "/commercial";
  try {
    const origin=new URL(currentOrigin);
    const previous=new URL(referrer);
    const approvedOrigin =
      (origin.protocol==="https:" &&
        (origin.hostname==="empire-ai.co.uk" || origin.hostname==="www.empire-ai.co.uk")) ||
      (origin.protocol==="http:" &&
        (origin.hostname==="127.0.0.1" || origin.hostname==="localhost"));
    if(!approvedOrigin) return "/commercial";
    if(previous.origin!==origin.origin) return "/commercial";
    if(previous.username || previous.password) return "/commercial";
    return REVIEWED_ENTRY_PAGES.includes(
      previous.pathname as (typeof REVIEWED_ENTRY_PAGES)[number],
    ) ? previous.pathname as (typeof REVIEWED_ENTRY_PAGES)[number] : "/commercial";
  } catch {return "/commercial";}
}
