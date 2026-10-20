/** Privacy-safe, text-only ROI conversation pilot.
 * Reuses the published deterministic guidance; no LLM or network transport.
 * Replies explain visitor assumptions, never imply actual sales or commitments.
 */
import type { RoiInputs, RoiScenario } from "./roi-assessment";
import { answerAssessmentQuestion, type RoiQuestion } from "./roi-guidance";

export type Qualification = {
  sector: "Roofing" | "Solar" | "HVAC" | "Dental" | "Other B2B" | null;
  challenge: "Qualifying enquiries" | "Slow follow-up" | "Measuring conversion" | "Understanding costs" | null;
  timing: "Exploring" | "Within 3 months" | "This month" | null;
};

export const EMPTY_QUALIFICATION: Qualification = {
  sector: null, challenge: null, timing: null,
};

export function classifyRoiQuestion(raw: string): RoiQuestion | "product" | "pricing" | "consent" | "unknown" {
  const text = raw.toLowerCase().trim();
  if (!text || text.length > 220) return "unknown";
  if (/(guarantee|predict|forecast|probability|accurate|confidence|certain|real result)/.test(text)) return "predictive_intelligence";
  if (/(break.?even|pay.?back|worth|loss|profit|first.?year|return|roi)/.test(text)) return "break_even";
  if (/(assum|input|rate|cost saving|time sav|qualification lift|lead volume|deal|calcula|estimate)/.test(text)) return "key_assumptions";
  if (/(price|pricing|quote|fee|subscription|billing|contract)/.test(text)) return "pricing";
  if (/(privacy|data|track|stored|save|submit|personal|consent)/.test(text)) return "consent";
  if (/(empire|product|service|platform|how does it work|what do you do)/.test(text)) return "product";
  if (/(email|contact|follow.?up|speak|proposal|next step|call.?back|phone|human)/.test(text)) return "next_steps";
  return "unknown";
}

export function respondToRoiQuestion(
  raw: string, inputs: RoiInputs, base: RoiScenario,
  currency: "GBP" | "USD",
): string {
  const intent = classifyRoiQuestion(raw);
  if (["break_even", "key_assumptions", "predictive_intelligence", "next_steps"].includes(intent)) {
    return answerAssessmentQuestion(intent as RoiQuestion, inputs, base, currency);
  }
  if (intent === "product") return (
    "Empire AI presents evidence-led commercial intelligence and lead-qualification planning for businesses. " +
    "This assessment explores possible value using your figures; it is not an activated buyer network, " +
    "a promise of new customers or a substitute for a scoped human-led proposal. " +
    "You can review the product description under Predictive Revenue and our evidence approach under Trust."
  );
  if (intent === "pricing") return (
    "The monthly and setup cost fields are numbers you entered, not Empire AI pricing. " +
    "A founder-reviewed proposal can explain an appropriate scope and actual terms. " +
    "Nothing here accepts an order, takes payment or binds either party."
  );
  if (intent === "consent") return (
    "Your questions, business-fit answers and calculator assumptions stay in this browser. " +
    "This guide makes no network request or CRM entry. If you choose to open the separate business enquiry form, " +
    "you decide what information to enter and must separately consent to an email response."
  );
  return (
    "I can explain break-even, qualification assumptions, uncertainty, Empire AI's scope, " +
    "or how to request a nonbinding proposal. Try asking: 'Which assumptions drive my result?' " +
    "I can't verify company-specific outcomes or give binding terms."
  );
}

export function qualificationBrief(
  q: Qualification, inputs: RoiInputs, currency: "GBP" | "USD",
): string {
  const safe = (value: string | null) => value ?? "Not supplied";
  return [
    "Empire AI — optional enquiry preparation (not submitted)",
    "Industry: " + safe(q.sector),
    "Main business priority: " + safe(q.challenge),
    "Approximate timing: " + safe(q.timing),
    "Illustrative inputs only; no independently verified outcomes.",
    "Monthly enquiries entered: " + inputs.monthlyLeads,
    "Currently qualified (%): " + inputs.qualificationRatePct,
    "Qualified enquiry close rate (%): " + inputs.closeRatePct,
    "Currency shown (no exchange conversion): " + currency,
    "Only share information you choose in the separate consented business enquiry form.",
    "No contact details, callback request, forecast or agreement included.",
  ].join("\n");
}
