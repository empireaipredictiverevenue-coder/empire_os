/** Deterministic, local-only assessment guidance, not an AI forecast. */
import type { RoiInputs, RoiScenario } from "./roi-assessment";

export type RoiQuestion =
  "break_even" | "key_assumptions" | "predictive_intelligence" | "next_steps";

export type RoiGuidance = {
  base: RoiScenario;
  contributionPerQualificationPoint: number;
  estimatedMonthlyLabourSaving: number;
  firstYearBreakEvenLiftPoints: number | null;
  breakEvenExplanation: string;
  riskNotes: readonly string[];
};

const money = (value: number, currency: "GBP" | "USD"): string =>
  new Intl.NumberFormat(currency === "GBP" ? "en-GB" : "en-US", {
    style: "currency", currency, maximumFractionDigits: 0,
  }).format(value);

const pct = (value: number): string =>
  new Intl.NumberFormat("en-GB", { maximumFractionDigits: 2 }).format(value);

export function buildRoiGuidance(
  inputs: RoiInputs,
  base: RoiScenario,
): RoiGuidance {
  const contributionPerQualificationPoint =
    (inputs.monthlyLeads / 100) *
    (inputs.closeRatePct / 100) *
    inputs.contributionPerDeal;
  const availableLiftPoints = 100 - inputs.qualificationRatePct;
  const firstYearFixedMonthly = inputs.monthlySolutionCost +
    inputs.oneTimeSetupCost / 12;
  const requiredContribution = Math.max(
    0, firstYearFixedMonthly - base.labourSavings,
  );
  const needed = requiredContribution === 0 ? 0
    : contributionPerQualificationPoint > 0
      ? requiredContribution / contributionPerQualificationPoint
      : null;
  const firstYearBreakEvenLiftPoints =
    needed !== null && needed <= availableLiftPoints ? needed : null;

  const notes: string[] = [];
  if (inputs.monthlyLeads === 0) {
    notes.push("No enquiries are entered; additional qualified sales and time savings cannot be estimated.");
  }
  if (inputs.closeRatePct === 0 || inputs.contributionPerDeal === 0) {
    notes.push("No added sales contribution can be estimated with a zero close rate or deal contribution.");
  }
  if (inputs.minutesPerLead === 0 || inputs.loadedHourlyCost === 0) {
    notes.push("The entered review time or labour cost is zero; this assessment cannot value saved time.");
  }
  if (inputs.monthlySolutionCost === 0 && inputs.oneTimeSetupCost === 0) {
    notes.push("No implementation or recurring costs are entered; comparisons to a real proposal need those costs.");
  }
  if (base.firstYearNet < 0) {
    notes.push("Your base-case assumptions indicate a first-year loss after the stated costs.");
  } else if (base.firstYearNet > 0) {
    notes.push("Your base case is positive only under your assumptions; it is not a measured outcome.");
  }
  if (firstYearBreakEvenLiftPoints === null) {
    notes.push("First-year break-even is not achievable from qualification-rate uplift alone within the entered bounds and time-saving assumptions.");
  }

  const explanation =
    firstYearBreakEvenLiftPoints === null
      ? "No feasible qualification-rate uplift alone breaks even in year one using your present lead volume, contribution, labour savings and costs. Revisit assumptions or scope."
      : firstYearBreakEvenLiftPoints === 0
        ? "Your assumed labour saving alone covers recurring and one-off costs when spread over the first 12 months. This is conditional, not verified."
        : `To reach first-year break-even under your other assumptions, the qualified share would need to rise by about ${pct(firstYearBreakEvenLiftPoints)} percentage points, from ${pct(inputs.qualificationRatePct)}% to ${pct(inputs.qualificationRatePct + firstYearBreakEvenLiftPoints)}%.`;

  return {
    base, contributionPerQualificationPoint,
    estimatedMonthlyLabourSaving: base.labourSavings,
    firstYearBreakEvenLiftPoints,
    breakEvenExplanation: explanation,
    riskNotes: notes,
  };
}

export type RoiAction = {
  priority: 1 | 2 | 3;
  title: string;
  why: string;
  suggestedTest: string;
  evidenceBasis: "VISITOR_ASSUMPTION";
};

/** Turn the visitor's exact figures into next-step hypotheses, never promises. */
export function buildRoiActionPlan(
  inputs: RoiInputs, base: RoiScenario,
): readonly RoiAction[] {
  const reviewHours = inputs.monthlyLeads * inputs.minutesPerLead / 60;
  const baseline: RoiAction = {
    priority: 1,
    title: "Verify your current enquiry baseline",
    why: inputs.monthlyLeads > 0
      ? `You entered ${inputs.monthlyLeads} enquiries per month, ${inputs.qualificationRatePct}% qualified and ${inputs.closeRatePct}% of qualified enquiries won.`
      : "You entered no monthly enquiries, so the assessment cannot estimate additional deals.",
    suggestedTest: inputs.monthlyLeads > 0
      ? "Use your last 30 days of enquiries to check the source, qualified share, won deals, actual contribution and time spent."
      : "Verify whether enquiries are being captured and recorded, then measure a real baseline before estimating qualification gains.",
    evidenceBasis: "VISITOR_ASSUMPTION",
  };

  let leverage: RoiAction;
  if (inputs.monthlyLeads === 0) {
    leverage = {
      priority: 2,
      title: "Validate the enquiry and offer journey",
      why: "Without observed enquiry volume, conversion or labour-savings estimates are not actionable.",
      suggestedTest: "Check that visitors can understand the offer, contact the business, and receive a human response. Track genuine enquiries without manufacturing leads.",
      evidenceBasis: "VISITOR_ASSUMPTION",
    };
  } else if (base.incrementalContribution <= 0 && base.labourSavings <= 0) {
    leverage = {
      priority: 2,
      title: "Find a measurable improvement before investing",
      why: "The entered assumptions produce no additional monthly sales contribution or valued time saving.",
      suggestedTest: "Observe real qualification and manual-review work first. Keep a proposed solution optional until you have a plausible, testable improvement.",
      evidenceBasis: "VISITOR_ASSUMPTION",
    };
  } else if (base.incrementalContribution >= base.labourSavings) {
    leverage = {
      priority: 2,
      title: "Test a consistent qualification process",
      why: `The assumed additional contribution is higher than the time-saving value in the base case. Current manual review represents about ${reviewHours.toFixed(1)} hours per month from your inputs.`,
      suggestedTest: "On a small, consented set of genuine enquiries, compare the percentage correctly qualified and subsequently closed against your existing baseline. Do not change buyer criteria without agreement.",
      evidenceBasis: "VISITOR_ASSUMPTION",
    };
  } else {
    leverage = {
      priority: 2,
      title: "Measure manual review time before automating",
      why: `Your assumptions suggest saved review time is the larger source of potential value, with about ${reviewHours.toFixed(1)} current review hours per month.`,
      suggestedTest: "Time a small set of real qualification tasks and estimate which hours could actually be redeployed or removed. Do not treat freed time as automatically received cash.",
      evidenceBasis: "VISITOR_ASSUMPTION",
    };
  }

  const economics: RoiAction = base.firstYearNet <= 0 ? {
    priority: 3,
    title: "Review costs and risk before commissioning",
    why: "At the stated assumptions, the base case does not show a positive first-year net benefit after recurring and setup costs.",
    suggestedTest: "Request a smaller scope or measured proof-of-value, and verify a realistic delivery cost before making any purchase decision.",
    evidenceBasis: "VISITOR_ASSUMPTION",
  } : {
    priority: 3,
    title: "Run a bounded proof-of-value with real outcomes",
    why: "The base case is positive only as an illustrative scenario, not as evidence of a realised customer return.",
    suggestedTest: "Track original source, consented enquiries, actual qualified outcomes, closed sales, delivery costs and staff time in a defined small pilot. Review with a person before contracting.",
    evidenceBasis: "VISITOR_ASSUMPTION",
  };
  return [baseline, leverage, economics];
}

export function answerAssessmentQuestion(
  question: RoiQuestion, inputs: RoiInputs, base: RoiScenario,
  currency: "GBP" | "USD" = "GBP",
): string {
  const d = buildRoiGuidance(inputs, base);
  if (question === "break_even") return (
    d.breakEvenExplanation +
    " The calculation covers your first-year recurring cost plus one-off setup; it does not imply a forecast or a promised saving."
  );
  if (question === "key_assumptions") return (
    `At the current close rate and contribution, every 1 percentage-point improvement in the qualified share adds ${money(d.contributionPerQualificationPoint, currency)} of potential monthly sales contribution. ` +
    `Your assumed saved qualification time contributes ${money(d.estimatedMonthlyLabourSaving, currency)} per month. ` +
    "The biggest uncertainties are whether the qualification improvement actually happens, whether saved time reduces real costs, and whether the extra deals close."
  );
  if (question === "predictive_intelligence") return (
    "Not yet. The preview uses your own assumptions, not a calibrated EmpireOS buyer-specific forecast. " +
    "Search, Market, Competitor, Buyer, Opportunity and Economic Memory evidence can enrich a future assessment " +
    "only when it is suitable for the visitor and approved for public use. Missing evidence is never treated as zero or invented probability."
  );
  return (
    "This assessment stays in your browser. No business figures have been sent to Empire AI. " +
    "You can save the worksheet locally, then choose whether to use the existing /commercial founder-led enquiry form. " +
    "The form is separate; you decide what to share. Scope, terms and prices are reviewed by a person."
  );
}

export function exportAssessmentText(
  inputs: RoiInputs, scenarios: readonly RoiScenario[],
  currency: "GBP" | "USD" = "GBP",
): string {
  const base = scenarios.find(row=>row.name==="Base case");
  if (!base || scenarios.length!==3) throw Error("Three validated scenarios required");
  const guidance = buildRoiGuidance(inputs, base);
  const lines = [
    "EMPIRE AI — REVENUE OPPORTUNITY ASSESSMENT",
    "Illustrative, visitor-supplied assumptions only. NOT a forecast or verified ROI.",
    "No customer data or private EmpireOS model results are included.",
    "Currency units: " + currency + " (no exchange conversion)",
    "",
    "YOUR ASSUMPTIONS",
    ...Object.entries(inputs).map(([key,value])=>`${key}: ${value}`),
    "",
    "ILLUSTRATIVE SCENARIOS (MONTHLY EXCEPT WHERE STATED)",
  ];
  for (const r of scenarios) {
    lines.push(
      r.name,
      "Additional deals per month: " + r.estimatedAdditionalDeals.toFixed(2),
      "Monthly sales contribution: " + money(r.incrementalContribution,currency),
      "Potential monthly labour saving: " + money(r.labourSavings,currency),
      "Monthly solution cost: " + money(inputs.monthlySolutionCost,currency),
      "Net monthly benefit: " + money(r.netMonthlyBenefit,currency),
      "First-year net after setup: " + money(r.firstYearNet,currency),
      "Payback on one-off setup: " +
        (r.paybackMonths === null ? "Not established" : pct(r.paybackMonths)+" months"),
      "",
    );
  }
  lines.push("FIRST-YEAR BREAK-EVEN",guidance.breakEvenExplanation,"",
    "THREE TESTABLE NEXT STEPS");
  for (const item of buildRoiActionPlan(inputs, base)) {
    lines.push(`${item.priority}. ${item.title}`, item.why,
      "Suggested check: " + item.suggestedTest,
      "Evidence classification: " + item.evidenceBasis, "");
  }
  lines.push("IMPORTANT LIMITATIONS",
    "Estimated contribution is not revenue received.",
    "Freed staff time is not necessarily realisable cash savings.",
    "Any projections depend entirely on your editable assumptions.",
    "No market, buyer or competitor evidence is automatically connected yet.",
    "Request a founder-reviewed, nonbinding proposal: https://empire-ai.co.uk/commercial",
    "",
  );
  return lines.join("\n");
}
