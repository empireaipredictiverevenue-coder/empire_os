import type { Metadata } from "next";
import RoofingHomeownerGuide, { type RoofingGuideSection } from "@/components/RoofingHomeownerGuide";

export const metadata: Metadata = {
  title: "Roof Repair vs Replacement: Homeowner Decision Guide | Empire AI",
  description: "Understand when a roofing repair may be reasonable, when a replacement assessment is worth considering, and what to ask before agreeing to work.",
  alternates: { canonical: "/roofing/replacement-vs-repair" },
  // Educational content is prepared for review, not yet approved for search indexation.
  robots: { index: false, follow: false },
  openGraph: {
    title: "Roof Repair or Full Replacement? Questions for Homeowners",
    description: "A practical checklist for comparing roofing repair and replacement options without assuming a remote diagnosis.",
    url: "/roofing/replacement-vs-repair",
    type: "article",
  },
};

const sections: RoofingGuideSection[] = [
  {
    heading: "Start with what has actually changed",
    paragraphs: [
      "A visible stain, a missing shingle and repeated leaks can each have different causes. Describe when the problem began, where it appears and whether it followed wind, hail or another weather event. Photographs from inside the property or safely from the ground can help a roofer understand the concern.",
      "Do not climb onto a damaged or wet roof to inspect it. A qualified local professional should assess the roof covering, flashing, drainage, ventilation and any concealed damage before recommending the scope of work.",
    ],
    checklist: [
      "Note the date, location and pattern of any leak or visible damage.",
      "Record prior repairs and any known age or warranty details.",
      "Keep photographs taken from safe, accessible locations.",
    ],
  },
  {
    heading: "When a focused roof repair may make sense",
    paragraphs: [
      "A repair may be appropriate when damage is limited to a specific area and the remaining roof is in serviceable condition. Examples could include an isolated flashing fault or a small section of damaged roofing material, but the surrounding system still needs inspection.",
      "Ask the contractor what the proposed repair fixes, what it does not address and how they will check for related moisture or underlayment problems. A lower initial quote is only useful if it addresses the underlying defect.",
    ],
    checklist: [
      "Request the exact repair area, materials and labour scope in writing.",
      "Ask whether the repair affects any existing roof warranty.",
      "Confirm whether there is a plan to check the result after completion.",
    ],
  },
  {
    heading: "When a replacement assessment is worth getting",
    paragraphs: [
      "Repeated failures across several areas, widespread deterioration or substantial underlying damage may justify comparing a full replacement with ongoing repairs. Roof age alone cannot settle the decision: material type, climate, workmanship, maintenance and actual condition all matter.",
      "Get a clear explanation of what the inspection found, including whether roof decking, ventilation, flashing or drainage need attention. If replacement is proposed, ask for a written scope and an alternative opinion when practical.",
    ],
    checklist: [
      "Compare the expected lifespan and limitations of the proposed options.",
      "Check whether removal and disposal of existing material are included.",
      "Ask what happens if concealed damaged decking is discovered.",
    ],
  },
  {
    heading: "Compare written estimates on the same scope",
    paragraphs: [
      "Estimates can look very different because they include different work. Compare materials, underlayment, flashing, ventilation, disposal, permits where required, insurance evidence, timelines and workmanship warranties rather than only the total price.",
      "Clarify who is responsible for any permits and inspections required locally. For storm-related damage, review your own insurance policy and contact your insurer directly; do not assume a contractor's estimate establishes coverage or claim eligibility.",
    ],
    checklist: [
      "Ask for an itemised estimate with exclusions and change-order rules.",
      "Verify the contractor's licensing or registration where locally required.",
      "Keep the proposed payment milestones, warranty and dispute process in writing.",
    ],
  },
];

export default function RoofRepairVsReplacementPage() {
  return (
    <RoofingHomeownerGuide
      eyebrow="US homeowner guide · Roof condition"
      title="Roof repair or replacement? How to compare the options"
      introduction="A roof problem does not automatically mean you need a whole new roof. Use this practical guide to ask better questions and compare professional assessments before committing to repair or replacement work."
      takeaway="Find the underlying problem first, then compare written scopes and long-term value. Neither a photograph nor a general checklist can replace an on-site inspection."
      sections={sections}
      nextGuide={{ href: "/roofing/installation-checklist", label: "Read the roof installation checklist" }}
    />
  );
}
