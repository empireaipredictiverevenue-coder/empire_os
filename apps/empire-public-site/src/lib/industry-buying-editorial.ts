/**
 * Original, educational first-party industry SEO copy for review.
 * Copy ≠ payable lead, customer case study, buying contract or site launch.
 * This asset is presented on B2B industry pages only; the held /roofing
 * consumer acquisition page and its noindex policy are never touched.
 */
export type BuyerEditorialSection = {
  heading: string;
  body: string;
  points?: readonly string[];
};

export type BuyerEditorial = {
  eyebrow: string;
  heading: string;
  introduction: string;
  sections: readonly BuyerEditorialSection[];
  questions: readonly { question: string; answer: string }[];
  commercialPrompt: string;
};

const roofing: BuyerEditorial = {
  eyebrow: "ROOFING BUYER ECONOMICS",
  heading: "From a roofing search to a qualified commercial opportunity.",
  introduction:
    "A homeowner searching for a roof replacement is not automatically a qualified call, booked appointment or paying buyer event. Better acquisition starts by checking source, service type, location and capacity against a specific buyer's written rules.",
  sections: [
    {
      heading: "Search intent and the actual job",
      body:
        "Roof repair, full replacement, installation and storm restoration are different jobs. A search impression shows visibility and an organic visit shows engagement; neither means a household has agreed to a quote or a roofing contractor has accepted a job.",
      points: [
        "Record the original first-party page and what the customer actually requested.",
        "Check whether the requirement matches the buyer's eligible roofing services.",
        "Keep estimated opportunity separate from a verified, consented enquiry.",
      ],
    },
    {
      heading: "Territory is more than a ZIP code",
      body:
        "A contractor may buy certain services in specific ZIP codes during defined hours. A buyer network may advertise national coverage while a particular campaign only accepts a narrow territory. Capacity, exclusions and current routing arrangements need written confirmation before a live test.",
      points: [
        "Match each service to a named accepting buyer and currently active coverage area.",
        "Verify hours, caps, duplications, transfers and any exclusions.",
        "Do not quote payout values until the buyer's applicable terms are established.",
      ],
    },
    {
      heading: "What makes a roofing call payable?",
      body:
        "A call ringing is not revenue. Whether a connected call is payable depends on the buyer's agreement: allowed source, customer intent, duration or outcome threshold, call handling, invalid calls, return window and settlement terms. Recording and transfer obligations also require location-specific review.",
      points: [
        "Keep attribution attached to the actual source and consent evidence.",
        "Reconcile buyer acceptance, disputes and reversals before counting revenue.",
        "Use approved reporting instead of assumed call values or fabricated conversion rates.",
      ],
    },
  ],
  questions: [
    {
      question: "Are organic roofing clicks paid pay-per-call events?",
      answer:
        "No. Search Console reports search visits, not billable buyer calls. Payment requires an agreed call campaign and independently accepted event evidence.",
    },
    {
      question: "Can every US roofing ZIP code be monetised?",
      answer:
        "No. Accepted territory, work categories, first-party traffic source, capacity, consent and payment rules must be verified for the particular buyer.",
    },
    {
      question: "Does a roofing demand forecast guarantee appointments?",
      answer:
        "No. A forecast highlights possible demand; verified appointments and collected revenue are distinct commercial outcomes.",
    },
  ],
  commercialPrompt:
    "Discuss a scoped roofing territory or buyer-corridor review. This is a nonbinding business enquiry, not an offer of pre-approved homeowner calls.",
};

const solar: BuyerEditorial = {
  eyebrow: "SOLAR BUYER AND PUBLISHER INTELLIGENCE",
  heading: "Solar referrals only become revenue when the buyer accepts the outcome.",
  introduction:
    "Solar searches can show interest in panels, batteries, installation quotes or home-energy savings. But an interested visitor, an accepted lead, a booked consultation and a completed installation are different stages. Their economics depend on the actual programme and geography.",
  sections: [
    {
      heading: "Confirm the installer and the territory",
      body:
        "Solar coverage is local. A UK programme may need postcode coverage and relevant installer accreditations; US programmes can depend on states, ZIP codes, utilities and service capacity; Australian partners can operate by state or installer network. Never assume one country's offer applies to another.",
      points: [
        "Confirm an accepting programme and eligible installer coverage for the actual region.",
        "Identify the system type, excluded jobs and current buyer capacity.",
        "Use the partner's written source and settlement terms, not a public headline rate.",
      ],
    },
    {
      heading: "Separate clicks, leads, appointments and installs",
      body:
        "A website visit is not a payable solar click unless a specific advertiser agreed to pay for verified outbound clicks. Many solar partnerships instead pay for accepted enquiries, consultations or completed installations. The applicable event and evidence must be unambiguous before traffic is routed.",
      points: [
        "Record consent for any onward sharing before a customer enquiry is transferred.",
        "Distinguish accepted leads from duplicate or unsuitable enquiries.",
        "Account for cancellation, reversal and payment timing in publisher economics.",
      ],
    },
    {
      heading: "Build referrals people can trust",
      body:
        "A useful comparison explains installer eligibility, location constraints and what happens after a customer contacts a partner. If a referral eventually earns Empire AI a commission, that commercial relationship should be clearly disclosed. Paid affiliate links need the appropriate sponsored link treatment and a verified destination.",
      points: [
        "Explain to users what information is shared and why.",
        "Keep commercial claims aligned to independently verifiable partner evidence.",
        "Avoid premature forms, outbound redirects and payment claims before approval.",
      ],
    },
  ],
  questions: [
    {
      question: "Does every solar website click earn a PPC commission?",
      answer:
        "No. A website click is a visit. Paid-per-click, pay-per-lead and installation commission are different agreements, each with its own payable event and rules.",
    },
    {
      question: "Can UK and Australian solar enquiries use the same buyer?",
      answer:
        "Not automatically. Installer coverage, country-specific consent, source approval and commercial terms must be checked independently.",
    },
    {
      question: "Can a public affiliate programme page prove an Empire AI payout?",
      answer:
        "No. A programme listing is research evidence, not proof of Empire AI acceptance, a signed rate or a settled commission.",
    },
  ],
  commercialPrompt:
    "Discuss a solar market, installer-coverage or referral-economics review. No affiliate clickout or homeowner data transfer is enabled from this page.",
};

export function getBuyerEditorial(slug: string): BuyerEditorial | null {
  if (slug === "roofing") return roofing;
  if (slug === "solar") return solar;
  return null;
}
