/** Public, client-only, deterministic ROI scenario maths.
 * No backend data, forecast or customer event is imported into this module.
 * All values are visitor-owned assumptions, not Empire AI observed revenue.
 */
export type RoiInputs = {
  monthlyLeads: number;
  qualificationRatePct: number;
  closeRatePct: number;
  contributionPerDeal: number;
  minutesPerLead: number;
  loadedHourlyCost: number;
  monthlySolutionCost: number;
  oneTimeSetupCost: number;
  qualificationLiftPoints: number;
  reviewTimeSavedPct: number;
};

export const ILLUSTRATIVE_INPUTS: RoiInputs = Object.freeze({
  monthlyLeads: 200,
  qualificationRatePct: 30,
  closeRatePct: 20,
  contributionPerDeal: 800,
  minutesPerLead: 12,
  loadedHourlyCost: 25,
  monthlySolutionCost: 350,
  oneTimeSetupCost: 1200,
  qualificationLiftPoints: 5,
  reviewTimeSavedPct: 25,
});

export type RoiScenario = {
  name: "Conservative" | "Base case" | "Optimistic";
  multiplier: number;
  baselineWonDeals: number;
  estimatedAdditionalQualifiedLeads: number;
  estimatedAdditionalDeals: number;
  incrementalContribution: number;
  labourSavings: number;
  grossMonthlyBenefit: number;
  netMonthlyBenefit: number;
  firstYearNet: number;
  paybackMonths: number | null;
  firstYearReturnPct: number | null;
  assumedQualificationPct: number;
  assumedTimeSavedPct: number;
};
export type EvidenceKind = "USER_ASSUMPTION" | "OBSERVED_AGGREGATE" | "VERIFIED_OUTCOME" | "UNAVAILABLE";
export type PublicIntelligenceContext = {
  source: "SEARCH_INTELLIGENCE" | "MARKET_INTELLIGENCE" | "COMPETITOR_INTELLIGENCE" |
    "BUYER_INTELLIGENCE" | "PREDICTIVE_INTELLIGENCE" | "OPPORTUNITY_INTELLIGENCE" | "ECONOMIC_MEMORY";
  classification: EvidenceKind;
  summary: string;
  evidenceRefs: string[];
  observedAt: string | null;
  publicUseAuthorized: boolean;
};

export const PREVIEW_INTELLIGENCE_CONTEXT: readonly PublicIntelligenceContext[] = Object.freeze([
  { source: "SEARCH_INTELLIGENCE", classification: "UNAVAILABLE", summary: "No source-verified search context supplied for this visitor.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
  { source: "MARKET_INTELLIGENCE", classification: "UNAVAILABLE", summary: "No location-specific market evidence supplied.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
  { source: "COMPETITOR_INTELLIGENCE", classification: "UNAVAILABLE", summary: "No verified competitor comparison supplied.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
  { source: "BUYER_INTELLIGENCE", classification: "UNAVAILABLE", summary: "No consented, customer-specific buyer evidence supplied.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
  { source: "PREDICTIVE_INTELLIGENCE", classification: "UNAVAILABLE", summary: "A calibrated product probability is not available for this assessment.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
  { source: "OPPORTUNITY_INTELLIGENCE", classification: "UNAVAILABLE", summary: "Opportunity ranks are not treated as customer savings or sales forecasts.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
  { source: "ECONOMIC_MEMORY", classification: "UNAVAILABLE", summary: "No verified realised-revenue cohort is available for this visitor.", evidenceRefs: [], observedAt: null, publicUseAuthorized: false },
]);

const percentKeys = ["qualificationRatePct","closeRatePct","reviewTimeSavedPct"] as const;
const positiveCaps: Record<keyof RoiInputs, number> = {
  monthlyLeads: 100000, qualificationRatePct: 100, closeRatePct: 100,
  contributionPerDeal: 10000000, minutesPerLead: 1440, loadedHourlyCost: 100000,
  monthlySolutionCost: 10000000, oneTimeSetupCost: 10000000,
  qualificationLiftPoints: 100, reviewTimeSavedPct: 100,
};
export function validateRoiInputs(inputs: RoiInputs): void {
  for (const key of Object.keys(positiveCaps) as Array<keyof RoiInputs>) {
    const value = inputs[key];
    if (!Number.isFinite(value) || value < 0 || value > positiveCaps[key]) {
      throw Error(`Invalid ${key}: must be a finite nonnegative number at most ${positiveCaps[key]}`);
    }
  }
  if (inputs.qualificationLiftPoints + inputs.qualificationRatePct > 100) {
    // We clamp each scenario to a physical maximum; don't silently use
    // impossible inputs for the published base case.
    throw Error("Base-case qualification improvement cannot exceed 100% qualified.");
  }
  for (const key of percentKeys) {
    if (inputs[key] > 100) throw Error(`Invalid percentage: ${key}`);
  }
}

function buildScenario(
  inputs: RoiInputs, name: RoiScenario["name"], multiplier: number,
): RoiScenario {
  const assumedQualificationPct = Math.min(
    100, inputs.qualificationRatePct + inputs.qualificationLiftPoints * multiplier,
  );
  const assumedTimeSavedPct = Math.min(100, inputs.reviewTimeSavedPct * multiplier);
  const baselineWonDeals =
    inputs.monthlyLeads * inputs.qualificationRatePct / 100 * inputs.closeRatePct / 100;
  const estimatedAdditionalQualifiedLeads =
    inputs.monthlyLeads * (assumedQualificationPct - inputs.qualificationRatePct) / 100;
  const estimatedAdditionalDeals =
    estimatedAdditionalQualifiedLeads * inputs.closeRatePct / 100;
  const incrementalContribution = estimatedAdditionalDeals * inputs.contributionPerDeal;
  const labourSavings =
    inputs.monthlyLeads * inputs.minutesPerLead / 60 *
    inputs.loadedHourlyCost * assumedTimeSavedPct / 100;
  const grossMonthlyBenefit = incrementalContribution + labourSavings;
  const netMonthlyBenefit = grossMonthlyBenefit - inputs.monthlySolutionCost;
  const firstYearNet = netMonthlyBenefit * 12 - inputs.oneTimeSetupCost;
  const annualCosts = inputs.monthlySolutionCost * 12 + inputs.oneTimeSetupCost;
  return {
    name, multiplier, baselineWonDeals,
    estimatedAdditionalQualifiedLeads, estimatedAdditionalDeals,
    incrementalContribution, labourSavings, grossMonthlyBenefit,
    netMonthlyBenefit, firstYearNet,
    paybackMonths: netMonthlyBenefit > 0
      ? inputs.oneTimeSetupCost / netMonthlyBenefit : null,
    firstYearReturnPct: annualCosts > 0
      ? firstYearNet / annualCosts * 100 : null,
    assumedQualificationPct, assumedTimeSavedPct,
  };
}

export function calculateRoiScenarios(inputs: RoiInputs): RoiScenario[] {
  validateRoiInputs(inputs);
  return [
    buildScenario(inputs, "Conservative", 0.5),
    buildScenario(inputs, "Base case", 1),
    buildScenario(inputs, "Optimistic", 1.5),
  ];
}

/** Rejects private and unverified data before any future public UI binding. */
export function publicIntelligenceSignals(
  signals: readonly PublicIntelligenceContext[],
): PublicIntelligenceContext[] {
  return signals.filter(signal =>
    signal.publicUseAuthorized === true &&
    signal.classification !== "UNAVAILABLE" &&
    Boolean(signal.summary.trim()) &&
    signal.evidenceRefs.length > 0 &&
    Boolean(signal.observedAt && !Number.isNaN(Date.parse(signal.observedAt))),
  );
}
