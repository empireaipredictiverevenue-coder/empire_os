/**
 * Original Empire AI buying-intent explainer based on one genuine historical
 * Search Console topic. Not a restoration of the unverified /aeo URL.
 * Does not inspect customer identities, submit leads or claim live buyers.
 */
const evidenceSteps = [
  {
    number: "01",
    name: "Define the account and decision",
    detail:
      "Start with the business problem, the service or product you can actually deliver, the countries or territories you support and the kind of organisation that could buy it. A company appearing in a large total addressable market (TAM) list only establishes a possible fit.",
    check: "Can we identify the organisation and the buying problem from reliable evidence?",
  },
  {
    number: "02",
    name: "Distinguish intent from visibility",
    detail:
      "Company growth, a new office, recruiting and a change in technology can be useful research triggers. They do not prove the company is currently looking for your service. Stronger indicators are relevant, time-bound, first-party enquiries or appropriately sourced public procurement and buying requests.",
    check: "Does the evidence show an actual decision or merely an interesting event?",
  },
  {
    number: "03",
    name: "Test fit and buyer capacity",
    detail:
      "A prospective account may show interest but be outside the supported market, buying window or budget. A lead marketplace adds another test: an accepting downstream buyer must confirm eligibility, approved source, exclusions, capacity and what constitutes a billable event. Do not assume advertised coverage means a contract is active.",
    check: "Who can deliver or accept this opportunity under verified terms?",
  },
  {
    number: "04",
    name: "Keep decisions and outcomes separate",
    detail:
      "Record the source, observation date and reason for a qualified review. Mark unknowns clearly, check consent before contacting or sharing an individual's details, and seek human approval at decision points. A forecast, search impression, profile match or email reply is not a won customer or realised revenue.",
    check: "What evidence would confirm the next stage, and who must authorise it?",
  },
] as const;

const questions = [
  {
    question: "How do you find companies in your TAM that are ready to buy?",
    answer:
      "Start with a narrow ideal-customer profile, then verify relevant current triggers and an independently sourced buying request where available. Review whether the company, timing and service fit are real. Rank research candidates for human review; do not present predicted interest as an identified, consenting buyer.",
  },
  {
    question: "Does a website visit or keyword search prove B2B purchase intent?",
    answer:
      "No. Search Console measures visibility and search clicks at a site or reported page level. It does not identify the visiting company, grant permission to contact anyone, or establish a payable advertiser click. Any first-party enquiry must be independently recorded with appropriate consent and an actual commercial acceptance event.",
  },
  {
    question: "What should a buyer-intent research report contain?",
    answer:
      "The business question, scope and exclusions; the observation source and freshness; what each signal does and does not establish; probable alternative explanations; a documented review decision; and the evidence required before sales outreach, downstream transfer or a payment claim.",
  },
] as const;

export default function TamBuyingIntentEvidenceGuide() {
  return (
    <section
      aria-labelledby="tam-buyer-intent-heading"
      id="tam-buying-intent"
      className="relative mt-16 overflow-hidden rounded-[2rem] border border-cyan-300/15 bg-[linear-gradient(125deg,rgba(14,36,67,.86),rgba(2,8,23,.96)_65%)] p-6 sm:p-9 lg:p-12"
    >
      <div aria-hidden="true" className="pointer-events-none absolute -right-28 -top-36 size-80 rounded-full bg-cyan-400/[0.065] blur-3xl" />
      <div className="relative">
        <p className="text-[11px] font-black uppercase tracking-[0.23em] text-cyan-300">
          Empire AI / Buyer-intent research method
        </p>
        <h2
          id="tam-buyer-intent-heading"
          className="mt-5 max-w-4xl text-3xl font-semibold leading-tight tracking-[-0.04em] text-white sm:text-4xl"
        >
          Which companies in your total addressable market are actually ready to buy?
        </h2>
        <p className="mt-6 max-w-4xl text-base leading-8 text-white/65">
          A list of companies is not a pipeline. Buying intent needs current evidence of a
          relevant business decision, an eligible opportunity and an accountable next step.
          This four-part evaluation helps distinguish a useful account-research hypothesis
          from an enquiry, an accepted lead and money actually collected.
        </p>
        <ol className="mt-10 grid gap-4 md:grid-cols-2">
          {evidenceSteps.map((step) => (
            <li
              key={step.number}
              className="rounded-2xl border border-white/10 bg-[#07142f]/65 p-6 sm:p-7"
            >
              <span className="text-xs font-bold tracking-[0.15em] text-emerald-300">
                EVIDENCE {step.number}
              </span>
              <h3 className="mt-4 text-xl font-semibold tracking-[-0.02em] text-white/90">
                {step.name}
              </h3>
              <p className="mt-3 text-sm leading-7 text-white/60">{step.detail}</p>
              <p className="mt-5 border-t border-white/10 pt-4 text-sm leading-6 text-cyan-100/80">
                <strong className="font-semibold text-cyan-200">Review question: </strong>
                {step.check}
              </p>
            </li>
          ))}
        </ol>
        <div className="mt-12 border-t border-white/10 pt-10">
          <h3 className="text-2xl font-semibold tracking-tight text-white">
            Buyer-intent questions, answered
          </h3>
          <div className="mt-6 grid gap-5 lg:grid-cols-3">
            {questions.map(({ question, answer }) => (
              <article key={question} className="border-t border-cyan-300/15 pt-5">
                <h4 className="text-base font-semibold leading-6 text-cyan-100">{question}</h4>
                <p className="mt-3 text-sm leading-7 text-white/60">{answer}</p>
              </article>
            ))}
          </div>
        </div>
        <div className="mt-10 flex flex-col gap-4 rounded-2xl border border-emerald-300/15 bg-emerald-300/[0.045] p-5 sm:flex-row sm:items-center sm:justify-between sm:p-7">
          <p className="max-w-2xl text-sm leading-7 text-white/70">
            <strong className="text-white">Need to assess a real market?</strong> Describe the
            region, eligible buyer or product, business decision and evidence you already have.
            A scoped enquiry is not a purchase, a verified downstream-buyer contract or a guarantee.
          </p>
          <a
            href="#commercial-enquiry"
            className="inline-flex min-h-12 shrink-0 items-center justify-center rounded-full border border-cyan-300/50 px-5 text-sm font-semibold text-cyan-100 transition hover:border-cyan-100 hover:bg-cyan-300/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-cyan-300"
          >
            Discuss a scoped review
          </a>
        </div>
      </div>
    </section>
  );
}
