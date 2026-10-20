/** One-shot, user-initiated, same-tab handoff into the existing commercial form.
 * Strict enum allowlists prevent arbitrary ROI/chat text or PII being stored.
 * Nothing is posted or saved to EmpireOS by this helper.
 */
export const ROI_ENQUIRY_DRAFT_KEY = "empire_roi_commercial_draft_v1";
export const ROI_ENQUIRY_DRAFT_TTL_MS = 15 * 60 * 1000;

export const ROI_ENQUIRY_SECTORS = ["Roofing", "Solar", "HVAC", "Dental", "Other B2B"] as const;
export const ROI_ENQUIRY_CHALLENGES = [
  "Qualifying enquiries", "Slow follow-up", "Measuring conversion", "Understanding costs",
] as const;
export const ROI_ENQUIRY_TIMINGS = ["Exploring", "Within 3 months", "This month"] as const;

export type RoiEnquirySelection = {
  sector: typeof ROI_ENQUIRY_SECTORS[number] | null;
  challenge: typeof ROI_ENQUIRY_CHALLENGES[number] | null;
  timing: typeof ROI_ENQUIRY_TIMINGS[number] | null;
};
export type RoiEnquiryDraft = {
  version: 1;
  createdAt: number;
  sector: typeof ROI_ENQUIRY_SECTORS[number];
  challenge: typeof ROI_ENQUIRY_CHALLENGES[number];
  timing: typeof ROI_ENQUIRY_TIMINGS[number];
};
type OneShotStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function member<T extends string>(allowed: readonly T[], value: unknown): value is T {
  return typeof value === "string" && allowed.includes(value as T);
}

/** Generates only fixed selection labels, not chat content or private numbers. */
export function makeRoiEnquiryDraft(
  selection: RoiEnquirySelection,
  createdAt: number = Date.now(),
): RoiEnquiryDraft | null {
  if (!member(ROI_ENQUIRY_SECTORS, selection.sector) ||
      !member(ROI_ENQUIRY_CHALLENGES, selection.challenge) ||
      !member(ROI_ENQUIRY_TIMINGS, selection.timing) ||
      !Number.isSafeInteger(createdAt) || createdAt <= 0) return null;
  return { version: 1, createdAt,
    sector: selection.sector, challenge: selection.challenge, timing: selection.timing };
}

/** Explicit action only; throws if browser storage is unavailable. */
export function saveRoiEnquiryDraft(storage: OneShotStorage, draft: RoiEnquiryDraft): void {
  storage.setItem(ROI_ENQUIRY_DRAFT_KEY, JSON.stringify(draft));
}

/** Consumes once, even if data is expired, malformed or from another version. */
export function consumeRoiEnquiryDraft(
  storage: OneShotStorage,
  now: number = Date.now(),
): RoiEnquiryDraft | null {
  const raw = storage.getItem(ROI_ENQUIRY_DRAFT_KEY);
  if (raw === null) return null;
  storage.removeItem(ROI_ENQUIRY_DRAFT_KEY);
  if (raw.length > 500 || !Number.isSafeInteger(now)) return null;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;
    const record = parsed as Record<string, unknown>;
    if (record.version !== 1 ||
        !Number.isSafeInteger(record.createdAt) ||
        (record.createdAt as number) > now ||
        now - (record.createdAt as number) > ROI_ENQUIRY_DRAFT_TTL_MS ||
        !member(ROI_ENQUIRY_SECTORS, record.sector) ||
        !member(ROI_ENQUIRY_CHALLENGES, record.challenge) ||
        !member(ROI_ENQUIRY_TIMINGS, record.timing)) return null;
    return parsed as RoiEnquiryDraft;
  } catch {
    return null;
  }
}

export function roiEnquiryOutcome(draft: RoiEnquiryDraft): string {
  return "Please review whether Empire AI can help with " + draft.challenge.toLowerCase() +
    " for our " + draft.sector + " business. Planning horizon: " + draft.timing +
    ". We would like an email-first, founder-reviewed discussion of fit, scope and a nonbinding proposal. " +
    "No estimated ROI or guaranteed outcome is claimed.";
}
