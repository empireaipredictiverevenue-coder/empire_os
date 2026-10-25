// Original Empire AI buyer education, separate from the immutable SEO
// Director release component. Editorial candidate only until website sign-off.
// Research concepts: ChartMogul NRR methodology and Amplitude funnel guide.
import { ownedRevenueGuideProposalHref } from "@/lib/commercial-entry-review";
// Jev public pain observations are hypotheses, NOT identified customers.
export default function SaaSRevenueLeakageGuide() {
  return (
    <section id="saas-revenue-diagnosis" aria-labelledby="saas-revenue-diagnosis-heading"
      className="mt-12 border-t border-blue-300/20 pt-9">
      <p className="text-xs font-semibold uppercase tracking-[.18em] text-cyan-300">
        SaaS revenue diagnosis · Evidence-led buyer guide
      </p>
      <h2 id="saas-revenue-diagnosis-heading"
        className="mt-3 max-w-4xl text-2xl font-semibold tracking-tight text-white md:text-3xl">
        Find the recurring-revenue leak before buying another growth tool
      </h2>
      <p className="mt-4 max-w-4xl text-sm leading-7 text-white/65">
        A company can win new accounts and still lose recurring revenue.
        These are practical investigation frameworks, not a diagnosis of a
        particular business or evidence that Empire AI has delivered a customer result.
      </p>
      <div className="mt-7 grid gap-5 lg:grid-cols-2">
        <article id="saas-lost-recurring-revenue"
          className="rounded-2xl border border-white/10 bg-[#07142f]/70 p-6 md:p-7">
          <h3 className="text-lg font-semibold text-[#bfdbfe]">
            Why is SaaS recurring revenue falling even when new sales are growing?
          </h3>
          <p className="mt-3 text-sm leading-7 text-white/65">
            New customer revenue can mask cancelled subscriptions and
            downgraded contracts. Start with the same opening customer cohort,
            then separate churn, contraction, expansion and any reactivation
            over a defined period. Do not mix revenue from new customers into
            net revenue retention for the opening cohort.
          </p>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-6 text-white/65">
            <li>Agree the reporting period, currency, recognised recurring-revenue definition and opening cohort.</li>
            <li>Reconcile signed subscription changes and credit notes against billing events, not forecasts.</li>
            <li>Compare gross retention (losses only) with net retention (including expansion) to locate a real gap.</li>
            <li>Assign owners to investigate each evidenced loss; track proposed fixes separately from recovered revenue.</li>
          </ol>
          <p className="mt-4 text-xs leading-6 text-white/45">
            Method reference:{" "}
            <a href="https://chartmogul.com/saas-metrics/nrr/"
              target="_blank" rel="noopener noreferrer"
              className="text-cyan-200 underline underline-offset-4 hover:text-white">
              ChartMogul's net revenue retention explanation
            </a>.
            Data definitions and reactivation treatment must be confirmed for your own billing system.
          </p>
        </article>
        <article id="saas-activation-friction"
          className="rounded-2xl border border-white/10 bg-[#07142f]/70 p-6 md:p-7">
          <h3 className="text-lg font-semibold text-[#bfdbfe]">
            Where does SaaS activation friction stop signups becoming paying users?
          </h3>
          <p className="mt-3 text-sm leading-7 text-white/65">
            Define an activation event that reflects first useful product value,
            rather than assuming that signing up, visiting a dashboard or
            clicking an email proves activation. Compare a permissioned signup
            cohort through onboarding, first-value completion, a real
            conversion event and a confirmed paid subscription.
          </p>
          <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm leading-6 text-white/65">
            <li>Choose the exact start event, meaningful activation event and time window before measuring.</li>
            <li>Measure stage-to-stage drop-off; examine segments without treating small samples as reliable conclusions.</li>
            <li>Check instrumentation, failed integrations and support blockers before redesigning an onboarding flow.</li>
            <li>Test a scoped change and compare genuine paid outcomes against the same cohort and attribution rules.</li>
          </ol>
          <p className="mt-4 text-xs leading-6 text-white/45">
            Method reference:{" "}
            <a href="https://amplitude.com/docs/quick-guides/build-your-first-funnel"
              target="_blank" rel="noopener noreferrer"
              className="text-cyan-200 underline underline-offset-4 hover:text-white">
              Amplitude's event-funnel documentation
            </a>.
            Product events are not payment or customer-consent evidence.
          </p>
        </article>
      </div>
      <div className="mt-6 rounded-2xl border border-blue-300/15 bg-blue-300/[.04] p-5 md:p-6">
        <h3 className="text-base font-semibold text-white">
          Request a scoped revenue diagnosis by email
        </h3>
        <p className="mt-2 max-w-3xl text-sm leading-7 text-white/65">
          If your organisation has a specific retention or activation question,
          describe the business goal, systems and geography using our existing
          deployment enquiry. Do not send raw customer records or confidential
          financial data in the form. Any data access, scope, delivery and cost
          need separate founder review. No conversion improvement is guaranteed.
        </p>
        <div className="mt-4 flex flex-wrap gap-4">
          <a href="#deployment-request"
            className="inline-flex text-sm font-semibold text-cyan-200 underline underline-offset-4 hover:text-white">
            Request a Predictive Revenue review
          </a>
          <a href={ownedRevenueGuideProposalHref()}
            className="inline-flex text-sm font-semibold text-cyan-200 underline underline-offset-4 hover:text-white">
            Request a commercial proposal
          </a>
        </div>
        <p className="mt-3 text-xs text-white/40">
          Buyer-initiated contact only. The form asks permission to respond
          to your specific enquiry, not consent to unrelated marketing.
        </p>
      </div>
    </section>
  );
}
