/** Editorial data only: never treat examples as campaigns, customer facts or legal advice. */
export type EvidenceStep = { name: string; evidence: string; notEnough: string };
export type GuideSection = { heading: string; paragraphs: string[]; checks?: string[] };
export type BuyerGuide = {
  slug: string;
  industry: "roofing" | "solar";
  eyebrow: string;
  metaTitle: string;
  metaDescription: string;
  title: string;
  accent: string;
  description: string;
  audience: string;
  focus: string;
  lead: string;
  steps: EvidenceStep[];
  sections: GuideSection[];
  faq: { question: string; answer: string }[];
  disclaimer: string;
};
export const guides: Record<"roofing" | "solar", BuyerGuide> = {
  roofing: {
    slug: "us-roofing-lead-qualification",
    industry: "roofing",
    eyebrow: "US Roofing · Evidence-Led Revenue",
    metaTitle: "US Roofing Lead Qualification: Calls, Appointments & Buyer Acceptance | Empire AI",
    metaDescription: "A practical US roofing lead qualification guide: distinguish clicks, homeowner enquiries, qualified calls, appointments and buyer-accepted outcomes.",
    title: "US roofing lead qualification: from the first click to a buyer-accepted opportunity",
    accent: "Know which roofing enquiries actually qualify.",
    description: "A practical evidence checklist for roofing operators, demand partners and commercial teams. Separate homeowner interest, genuine contact, service-area fit and agreed acceptance criteria before counting revenue.",
    audience: "Roofing operators, business-development teams and acquisition partners",
    focus: "A roofing lead is not automatically an accepted call, appointment or payable job.",
    lead: "A local search click, a homeowner callback request and a roofing contractor's accepted commercial opportunity are three different events. They need distinct evidence. A reliable buyer-quality programme explains where the enquiry came from, what the prospect asked for, what consent exists and what would make the receiving contractor accept or reject the opportunity.",
    steps: [
      { name: "1. Search or referral click", evidence: "First-party source attribution and a real visit.", notEnough: "A click does not establish roofing intent, a known person or a payable conversion." },
      { name: "2. Enquiry and relevance", evidence: "A declared roof problem, property location and the type of service requested.", notEnough: "An unverified form, bot interaction or unrelated home-improvement request." },
      { name: "3. Permission and connection", evidence: "Recorded communication permissions within the exact requested scope, plus an actual reachable contact.", notEnough: "An unchecked opt-in box, assumed consent or a call-start signal alone." },
      { name: "4. Buyer eligibility", evidence: "Verified service area, contractor capacity, job category and exclusions agreed in advance.", notEnough: "A zip-code match without evidence the buyer can actually service the job." },
      { name: "5. Accepted call or appointment", evidence: "Independent receiver-side connection or acknowledgement and the agreed acceptance event.", notEnough: "A connected caller leg, a calendar invite or an affiliate test reported as successful." },
      { name: "6. Earned revenue", evidence: "Contractual payable condition, accepted delivery and independently reconciled settlement.", notEnough: "Forecast value, estimated payout or an unaccepted test call." },
    ],
    sections: [
      {
        heading: "What should a roofing lead qualification checklist capture?",
        paragraphs: [
          "Start with the smallest details needed to decide whether an enquiry can be serviced. Typical questions cover the broad roof issue, whether the property is residential or commercial, the service area, approximate timing and whether the person wants a call or an inspection. Avoid requesting sensitive or unnecessary data at the first step.",
          "A homeowner enquiry and a B2B contractor request are not interchangeable. A homeowner asking for storm-damage repair belongs in a consumer service workflow. A roofing group asking for verified demand or territory forecasting belongs in a commercial proposal workflow. Empire AI's commercial form is for businesses, not for collecting homeowner leads on this page."
        ],
        checks: [
          "The stated service need matches a contractor's actual offered services.",
          "The lead's broad location is inside agreed and currently serviceable territory.",
          "The contact knows who may respond and what communication they asked for.",
          "Previous opt-outs, duplicates and exclusions have been checked before action.",
          "Acceptance criteria and any dispute window are agreed before an outcome is priced."
        ],
      },
      {
        heading: "How to evaluate pay-per-lead, pay-per-call and booked appointments",
        paragraphs: [
          "Pay-per-lead pays for an agreed qualifying enquiry, pay-per-call requires a defined call event and pay-per-appointment requires an agreed scheduled outcome. Those labels alone do not describe quality. Define the exact qualifying event, attribution, minimum connection evidence, geography, duplicate rule, consent and cancellation handling in writing.",
          "A call routed into a network is not proof that the buyer answered. A recorded appointment is not proof that the roofing work was completed. Request sample evidence that demonstrates the specific stage you are considering, with customer privacy protected."
        ],
      },
      {
        heading: "Which roofing signals justify the next action?",
        paragraphs: [
          "Signals should support a justified next step, not a made-up intent score. Service-area fit may justify a qualification review. A direct request for a quote may justify a scoped response through the channel the person selected. Only accepted terms and fulfilment evidence justify treating a transaction as earned.",
          "For roofing organisations evaluating acquisition or predictive demand, useful review topics include seasonality, territory capacity, verified contact rates and the difference between booked demand and accepted jobs. These are analysis questions, not claims that Empire AI has already delivered those outcomes."
        ],
      },
      {
        heading: "Commercial roofing demand assessment: what to prepare",
        paragraphs: [
          "A business requesting an Empire AI review can describe its operating regions, roofing services, existing enquiry channels, what makes a lead unacceptable and which outcome matters: qualified calls, buyer-confirmed appointments or measurable forecasting. We can then assess whether a nonbinding, founder-reviewed scope is appropriate.",
          "Do not submit homeowner contact details through the commercial proposal form. For US consumer calls, any separate partner-specific activation, recording notice and buyer acceptance require their own approvals and evidence."
        ],
        checks: [
          "List the contractor regions and service types you can genuinely support.",
          "Define a qualified lead, a qualified phone connection and an accepted booking separately.",
          "Identify your existing CRM and source-attribution limitations.",
          "Explain whether you need a one-time assessment, strategy work or ongoing advisory support."
        ],
      },
    ],
    faq: [
      { question: "Is every roofing form submission a payable lead?", answer: "No. Payment eligibility depends on pre-agreed source, service, permission, duplicate and buyer-acceptance conditions. A raw form count alone cannot establish those facts." },
      { question: "Does an answered phone call prove a buyer accepted the lead?", answer: "Not necessarily. The receiving buyer leg, eligibility, permitted recording or consent process and explicit commercial acceptance may be separate requirements." },
      { question: "Can Empire AI guarantee appointments or roofing revenue?", answer: "No. This page describes qualification and measurement methods. Any engagement needs scoped terms, practical delivery capacity and independently verified outcomes." },
    ],
    disclaimer: "This guide is business decision support, not legal advice or a customer case study. No buyer-leg routing, campaign payout or customer result is represented as independently verified here.",
  },
  solar: {
    slug: "us-solar-lead-appointment-qualification",
    industry: "solar",
    eyebrow: "US Solar · Evidence-Led Revenue",
    metaTitle: "US Solar Leads & Appointment Qualification Checklist | Empire AI",
    metaDescription: "Understand the steps from solar enquiry to installer-qualified appointment, customer consent, service-area fit and verifiable commercial acceptance.",
    title: "US solar lead and appointment qualification: an evidence-first checklist",
    accent: "An appointment only matters when it fits a real buyer.",
    description: "For solar companies and demand partners evaluating enquiries, booked appointments and downstream acceptance. Check qualification and permission before assigning commercial value.",
    audience: "Solar businesses, demand partners and revenue operations teams",
    focus: "An energy-interest click is not the same as an installer-qualified appointment.",
    lead: "Solar search traffic can include consumers comparing electricity bills, researching equipment, looking for incentives or seriously considering a rooftop project. Those intentions are different. A useful lead programme checks that the requested service, territory, contact permission and actual installer capacity line up before a booked appointment is called an accepted outcome.",
    steps: [
      { name: "1. Discovery click", evidence: "A real, attributed entry from relevant search, a referral or first-party content.", notEnough: "A click count or keyword ranking is not an installation enquiry." },
      { name: "2. Stated solar interest", evidence: "An explicit enquiry about a service such as an installer consultation or commercial-solar scope.", notEnough: "Browsing an incentives guide or watching a solar explainer." },
      { name: "3. Permission to respond", evidence: "Documented request and channel-specific contact consent, with any relevant suppression checked.", notEnough: "Consent inferred from a third-party directory or an unchecked box." },
      { name: "4. Installer fit", evidence: "A real accepting installer, service territory and minimum qualification requirements.", notEnough: "Assumed national coverage or a publisher without a contracted receiving buyer." },
      { name: "5. Installer-accepted appointment", evidence: "Buyer acknowledgement, scheduled appointment terms and any agreed qualification or rescheduling rules.", notEnough: "A lead routed to an unverified calendar or automated invitation." },
      { name: "6. Commercial settlement", evidence: "Buyer approval of the payable event, documented fulfilment and independent payment reconciliation.", notEnough: "Estimated commission, predicted close rate or unsigned commercial terms." },
    ],
    sections: [
      {
        heading: "What makes a US solar enquiry genuinely qualified?",
        paragraphs: [
          "The first review should distinguish consumer rooftop projects from commercial and industrial solar. A homeowner's rooftop inquiry may require an installer serving that property's region, while a commercial project may involve building ownership, energy demand, finance, procurement and technical feasibility. Do not reuse a residential qualification form as a commercial business contract.",
          "Depending on the project, a solar provider may need to verify location, utility territory, roof suitability and decision-maker authority. That assessment belongs with the appropriately authorised installer or commercial assessor. An initial Empire AI B2B proposal enquiry should not collect household electricity account numbers, personal roof images, financial records or other unnecessary consumer data."
        ],
        checks: [
          "Confirm whether the enquiry is residential, commercial or general information-seeking.",
          "Confirm the requested geography maps to a real installer service area.",
          "Identify what qualification questions the receiving buyer actually accepts.",
          "Document the permission basis for contact, suppression and record retention.",
          "Separate a consultation booked from a consultation attended and buyer accepted."
        ],
      },
      {
        heading: "Solar appointment setting versus accepted commercial outcomes",
        paragraphs: [
          "A calendar booking records an intended meeting. A qualified appointment additionally needs criteria that the installer agrees to evaluate. Depending on the commercial agreement, payment may depend on attendance, eligibility, appointment acceptance or a later event. These terms must be known before anyone describes the booking as payable revenue.",
          "Review duplicates, lead-source transparency, cancelled appointments, no-shows, opt-outs and any chargebacks or disputed records. The same enquiry should not be silently sold as multiple independent outcomes. Buyer acceptance and settlement should remain separately auditable stages."
        ],
      },
      {
        heading: "Solar lead consent and responsible follow-up",
        paragraphs: [
          "US solar outreach may be affected by federal and state telemarketing, privacy, recording and consent rules, which can vary by channel and circumstances. A website checklist cannot substitute for jurisdiction-specific legal advice or the partner's own documented policies.",
          "Give people clear information about who may contact them and for what purpose. Record the specific requested interaction, honour opt-outs and do not infer permission for unrelated marketing. Keep marketing attribution, qualified buyer acceptance and real settlement evidence separate."
        ],
      },
      {
        heading: "How a solar company can request an Empire AI assessment",
        paragraphs: [
          "If you operate a solar company or manage its commercial acquisition, bring a concise business brief: market, service regions, residential versus C&I scope, permitted lead sources, current qualification definitions and your desired measurable outcome. Empire AI can review whether demand intelligence, buyer qualification or governed workflow advisory fits that business problem.",
          "Use the existing founder-reviewed commercial proposal route. It is a B2B enquiry, not a consumer rooftop quote form, an installer matching service or a promise of lead volume."
        ],
        checks: [
          "Explain which solar segment and service territory you operate in.",
          "Identify your current contact, appointment and buyer acceptance definitions.",
          "Describe CRM tracking or data quality gaps without uploading household records.",
          "Say which decision you need support with and your preferred email contact."
        ],
      },
    ],
    faq: [
      { question: "Does a booked solar consultation count as verified revenue?", answer: "No. A booking is a scheduling event. Any accepted payable event and resulting settlement must be evidenced independently under real commercial terms." },
      { question: "Is a solar publisher automatically an installer or qualified buyer?", answer: "No. Publishers can attract enquiries without having a verified downstream installer, agreed service capacity or a binding buyer acceptance contract." },
      { question: "Can this guide replace federal and state consent checks?", answer: "No. This is an operational checklist, not legal advice. The relevant contact, privacy, recording and jurisdiction-specific requirements need their own qualified review." },
    ],
    disclaimer: "This page is business decision support, not consumer solar advice, legal guidance or a claim of installed panels, accepted appointments or earned commissions.",
  },
};
