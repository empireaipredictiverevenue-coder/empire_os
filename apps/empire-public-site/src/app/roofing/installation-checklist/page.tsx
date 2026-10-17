import type { Metadata } from "next";
import RoofingHomeownerGuide, { type RoofingGuideSection } from "@/components/RoofingHomeownerGuide";

export const metadata: Metadata = {
  title: "Roof Installation Checklist for Homeowners | Empire AI",
  description: "A practical roof installation checklist covering written estimates, materials, permits, on-site work, cleanup and final inspection questions.",
  alternates: { canonical: "/roofing/installation-checklist" },
  // Editorial staging only; do not imply approval or live contractor availability.
  robots: { index: false, follow: false },
  openGraph: {
    title: "Roof Installation Checklist: Before, During and After the Job",
    description: "Questions to ask a roofer before signing a roof installation contract and during final inspection.",
    url: "/roofing/installation-checklist",
    type: "article",
  },
};

const sections: RoofingGuideSection[] = [
  {
    heading: "Before choosing a roofing contractor",
    paragraphs: [
      "Start with an assessment of the property and a written explanation of the proposed roofing system. Contractors should be able to describe the existing roof condition, any planned tear-off, the replacement materials and why those choices fit the roof's shape, climate and intended use.",
      "Requirements vary by state, county and city. Verify relevant licence or registration status where required, insurance details and responsibility for local permits or inspections. Do not rely on a directory badge alone as proof of qualification.",
    ],
    checklist: [
      "Ask for a written estimate that separates included work from exclusions.",
      "Verify appropriate local credentials and insurance directly where possible.",
      "Check recent references and the proposed start and completion process.",
    ],
  },
  {
    heading: "Confirm the complete installation scope",
    paragraphs: [
      "A roof installation quote should explain the specified roof covering, underlayment, ice or water protection where applicable, flashing at openings and penetrations, roof-edge details, drainage and ventilation. Materials alone do not establish that the whole system will be installed correctly.",
      "Ask how hidden damage will be identified and priced if removing the old roof exposes deteriorated decking. Agree on who can approve a change order before extra work starts.",
    ],
    checklist: [
      "List material manufacturer, product specification and proposed colour.",
      "Identify decking repair allowances, flashing and ventilation work.",
      "Confirm disposal, property protection and weather contingency plans.",
      "Require written pricing and authorisation for unexpected changes.",
    ],
  },
  {
    heading: "Make the contract and payment terms clear",
    paragraphs: [
      "The agreement should identify the business performing the work, property, materials, total price or pricing method, schedule, payment milestones, cancellation terms and warranty coverage. Read what the workmanship warranty actually promises and how a claim would be handled.",
      "Local rules and standard payment practices vary. Avoid treating a verbal promise as a substitute for written terms, and do not pay the entire contract amount in advance without understanding the risk and local requirements.",
    ],
    checklist: [
      "Keep a signed copy of the estimate, contract and any change orders.",
      "Agree when progress and final payments become due.",
      "Find out who handles required permits and final inspections.",
    ],
  },
  {
    heading: "During the work and at final handover",
    paragraphs: [
      "Agree where materials will be stored, how gardens, vehicles and entrances will be protected, and whom to contact if weather or previously concealed damage changes the schedule. Keep children and pets clear of the work area and let the crew handle roof access.",
      "At handover, ask for an explanation of completed work, any outstanding items, photographs if available, cleanup confirmation and warranty documents. Confirm how to report a leak or workmanship concern after the installation.",
    ],
    checklist: [
      "Walk the accessible ground-level areas to check cleanup and debris removal.",
      "Confirm required inspection documentation, if applicable.",
      "Collect receipts, product details and written warranty information.",
      "Document any incomplete work and the agreed correction date.",
    ],
  },
];

export default function RoofInstallationChecklistPage() {
  return (
    <RoofingHomeownerGuide
      eyebrow="US homeowner guide · Planning and installation"
      title="Roof installation checklist: before, during and after the job"
      introduction="Replacing a roof is a major property decision. Use this checklist to compare installation proposals, clarify responsibilities and keep a useful record from initial inspection through final handover."
      takeaway="Make the installation scope, materials, local requirements, payment milestones and final handover measurable in writing before work begins."
      sections={sections}
      nextGuide={{ href: "/roofing/replacement-vs-repair", label: "Compare roof repair and replacement" }}
    />
  );
}
