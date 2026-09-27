"use client";

import {
  ArrowLeft,
  Building2,
  Check,
  LoaderCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Product = {
  product_code: string;
  name: string;
  deployment_price_cents: number;
  deployment_price_display: string;
  price_type: string;
  ideal_buyer: string;
  outcome: string;
  included_capabilities: string[];
  recurring_model: string;
  pricing_state: string;
  binding_terms_ready: boolean;
};

type Catalog = {
  products: Product[];
  product_count: number;
  pricing_authority: string;
  recurring_enterprise_pricing: string;
};

type IntakeResult = {
  decision?: string;
  prospect_id?: string;
  product_code?: string;
  product_name?: string;
  approved_entry_price_cents?: number;
  price_type?: string;
  detail?: string;
  error?: string;
};

const SYSTEM_OPTIONS = [
  "CRM",
  "Paid Ads",
  "Search / SEO",
  "Sales Calls",
  "Email / Outreach",
  "Finance / Revenue Data",
  "Data Warehouse",
  "Customer Success",
];

function human(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function shortName(name: string) {
  return name.replace("Predictive Revenue ", "");
}

export default function PredictiveRevenuePage() {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [productCode, setProductCode] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [domain, setDomain] = useState("");
  const [industry, setIndustry] = useState("");
  const [geography, setGeography] = useState("");
  const [revenueBand, setRevenueBand] = useState("unknown");
  const [desiredOutcome, setDesiredOutcome] = useState("");
  const [systems, setSystems] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<IntakeResult | null>(null);

  useEffect(() => {
    fetch("/v1/checkout/predictive-revenue/products")
      .then(async (response) => {
        if (!response.ok) throw new Error("catalog unavailable");
        return response.json();
      })
      .then((body: Catalog) => {
        setCatalog(body);
        if (body.products?.length) {
          setProductCode(body.products[0].product_code);
        }
      })
      .catch(() =>
        setCatalogError(
          "Predictive Revenue deployment catalogue is temporarily unavailable.",
        ),
      );
  }, []);

  const product = useMemo(
    () =>
      catalog?.products.find((item) => item.product_code === productCode) ||
      null,
    [catalog, productCode],
  );

  function toggleSystem(value: string) {
    setSystems((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value],
    );
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!product || submitting) return;

    setSubmitting(true);
    setResult(null);
    const idempotencyKey =
      globalThis.crypto?.randomUUID?.() ||
      `predictive-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    try {
      const response = await fetch(
        "/v1/checkout/predictive-revenue/interests",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            product_code: product.product_code,
            business_name: businessName,
            email,
            domain,
            industry,
            geography,
            annual_revenue_band: revenueBand,
            desired_outcome: desiredOutcome,
            systems,
            idempotency_key: idempotencyKey,
          }),
        },
      );
      const body = await response.json();
      setResult(
        response.ok
          ? body
          : {
              detail:
                body.detail ||
                body.error ||
                "Deployment request could not be recorded.",
            },
      );
    } catch {
      setResult({
        detail: "Predictive Revenue intake is temporarily unavailable.",
      });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-[#020817] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_78%_8%,rgba(37,99,235,.2),transparent_28%),radial-gradient(circle_at_12%_72%,rgba(6,182,212,.1),transparent_25%)]" />
      <div className="relative mx-auto max-w-7xl px-5 py-8 md:px-8 md:py-12">
        <div className="mb-10 flex items-center justify-between">
          <a
            href="/buy"
            className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-white/55 transition hover:text-white"
          >
            <ArrowLeft className="size-4" />
            EMPIRE COMMERCIAL PORTAL
          </a>
          <div className="inline-flex items-center gap-2 rounded-full border border-blue-300/20 bg-blue-300/[0.06] px-3 py-2 text-[9px] font-semibold tracking-[0.14em] text-blue-100">
            <ShieldCheck className="size-3.5" />
            PREDICTIVE REVENUE
          </div>
        </div>

        <section className="mb-12">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[#60a5fa]">
            FLAGSHIP ENTERPRISE PLATFORM
          </div>
          <h1 className="mt-4 max-w-5xl text-5xl font-medium leading-[.92] tracking-[-.055em] md:text-7xl">
            Predict revenue.
            <span className="block bg-gradient-to-r from-[#bfdbfe] via-[#93c5fd] to-[#67e8f9] bg-clip-text text-transparent">
              Prove what became real.
            </span>
          </h1>
          <p className="mt-6 max-w-3xl text-base leading-7 text-white/55">
            Empire connects commercial evidence across pipeline, search, demand,
            calls, customers, markets and outcomes to show what revenue is
            likely, what is at risk, where opportunity is emerging and what the
            real outcome taught the system.
          </p>
        </section>

        <div className="grid gap-10 xl:grid-cols-[1.15fr_.85fr]">
          <section>
            <div className="grid gap-3 md:grid-cols-2">
              {catalog?.products.map((item, index) => {
                const active = item.product_code === productCode;
                const final = index === catalog.products.length - 1;
                return (
                  <button
                    key={item.product_code}
                    type="button"
                    onClick={() => {
                      setProductCode(item.product_code);
                      setResult(null);
                    }}
                    className={
                      "rounded-2xl border p-5 text-left transition " +
                      (final ? "md:col-span-2 " : "") +
                      (active
                        ? "border-[#60a5fa]/45 bg-[#0b1f4b]/75 shadow-[0_0_45px_rgba(37,99,235,.12)]"
                        : "border-white/[0.08] bg-white/[0.025] hover:border-white/15")
                    }
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <strong className="block text-base font-semibold text-white">
                          {shortName(item.name)}
                        </strong>
                        <span className="mt-1.5 block text-xs text-white/36">
                          {human(item.ideal_buyer)}
                        </span>
                      </div>
                      <div className="text-xl font-semibold tracking-[-.03em] text-[#bfdbfe]">
                        {item.deployment_price_display}
                      </div>
                    </div>
                    <p className="mt-4 text-xs leading-5 text-white/48">
                      {item.outcome}
                    </p>
                    <div className="mt-4 flex flex-wrap gap-1.5">
                      {item.included_capabilities.slice(0, 5).map((capability) => (
                        <span
                          key={capability}
                          className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[9px] text-white/42"
                        >
                          {human(capability)}
                        </span>
                      ))}
                    </div>
                  </button>
                );
              })}

              {!catalog && !catalogError ? (
                <div className="flex items-center gap-3 rounded-2xl border border-white/[0.08] p-5 text-sm text-white/45 md:col-span-2">
                  <LoaderCircle className="size-4 animate-spin" />
                  Loading Predictive Revenue deployments…
                </div>
              ) : null}

              {catalogError ? (
                <div className="rounded-2xl border border-red-400/20 bg-red-400/[0.05] p-5 text-sm text-red-200 md:col-span-2">
                  {catalogError}
                </div>
              ) : null}
            </div>

            <div className="mt-6 rounded-3xl border border-white/[0.08] bg-white/[0.025] p-6">
              <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-[#93c5fd]">
                <Sparkles className="size-4" />
                WHAT EMPIRE IS BUILT TO ANSWER
              </div>
              <div className="mt-5 grid gap-3 text-sm leading-6 text-white/55 md:grid-cols-2">
                <div>What revenue is likely, from whom, where and when?</div>
                <div>Where is revenue leaking or becoming at risk?</div>
                <div>Which market, customer or channel matters next?</div>
                <div>Which action has the strongest evidence and economics?</div>
                <div>What actually became recognized revenue and gross profit?</div>
                <div>What did prediction-vs-actual teach the system?</div>
              </div>
            </div>
          </section>

          <section>
            <form
              onSubmit={submit}
              className="sticky top-8 rounded-3xl border border-white/[0.09] bg-[#07142f]/80 p-6 shadow-[0_30px_100px_rgba(0,0,0,.3)] backdrop-blur-xl md:p-8"
            >
              <div className="mb-6">
                <div className="flex items-center gap-2 text-xs font-semibold tracking-[0.14em] text-white/45">
                  <Building2 className="size-4" />
                  REQUEST DEPLOYMENT
                </div>
                <div className="mt-2 flex items-end justify-between gap-4">
                  <div className="text-lg font-semibold">
                    {product ? shortName(product.name) : "Select deployment"}
                  </div>
                  <div className="text-2xl font-semibold tracking-[-.04em] text-[#bfdbfe]">
                    {product?.deployment_price_display || "—"}
                  </div>
                </div>
                <p className="mt-2 text-xs leading-5 text-white/38">
                  This records a deployment request. It does not create a
                  contract, payment request or production deployment.
                </p>
              </div>

              <div className="grid gap-4">
                <Field label="Business">
                  <input
                    required
                    value={businessName}
                    onChange={(e) => setBusinessName(e.target.value)}
                    className="input"
                    placeholder="Example Group"
                  />
                </Field>
                <Field label="Work email">
                  <input
                    required
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input"
                    placeholder="you@company.com"
                  />
                </Field>
                <Field label="Company domain">
                  <input
                    required
                    value={domain}
                    onChange={(e) => setDomain(e.target.value)}
                    className="input"
                    placeholder="company.com"
                  />
                </Field>

                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Industry">
                    <input
                      required
                      value={industry}
                      onChange={(e) => setIndustry(e.target.value)}
                      className="input"
                      placeholder="Roofing, SaaS, PE…"
                    />
                  </Field>
                  <Field label="Geography">
                    <input
                      required
                      value={geography}
                      onChange={(e) => setGeography(e.target.value)}
                      className="input"
                      placeholder="UK, US, Europe…"
                    />
                  </Field>
                </div>

                <Field label="Approx annual revenue">
                  <select
                    value={revenueBand}
                    onChange={(e) => setRevenueBand(e.target.value)}
                    className="input"
                  >
                    <option value="unknown">Prefer not to say</option>
                    <option value="under_1m">Under $1m</option>
                    <option value="1m_5m">$1m–$5m</option>
                    <option value="5m_25m">$5m–$25m</option>
                    <option value="25m_100m">$25m–$100m</option>
                    <option value="100m_500m">$100m–$500m</option>
                    <option value="500m_plus">$500m+</option>
                  </select>
                </Field>

                <Field label="What do you want Predictive Revenue to improve?">
                  <textarea
                    required
                    value={desiredOutcome}
                    onChange={(e) => setDesiredOutcome(e.target.value)}
                    className="input min-h-28 resize-y"
                    placeholder="Forecast accuracy, pipeline conversion, market expansion, revenue leakage, portfolio intelligence…"
                  />
                </Field>

                <div>
                  <div className="mb-2 text-xs text-white/55">
                    Systems already in the business
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {SYSTEM_OPTIONS.map((item) => {
                      const active = systems.includes(item);
                      return (
                        <button
                          type="button"
                          key={item}
                          onClick={() => toggleSystem(item)}
                          className={
                            "rounded-full border px-3 py-2 text-[10px] transition " +
                            (active
                              ? "border-[#60a5fa]/45 bg-[#2563eb]/15 text-[#dbeafe]"
                              : "border-white/[0.08] bg-white/[0.02] text-white/40 hover:text-white")
                          }
                        >
                          {item}
                        </button>
                      );
                    })}
                  </div>
                </div>
              </div>

              <button
                disabled={!product || submitting}
                className="mt-7 inline-flex min-h-13 w-full items-center justify-center gap-2 rounded-xl bg-[#eaf2ff] px-5 text-xs font-bold tracking-[0.11em] text-[#07132c] transition enabled:hover:-translate-y-0.5 enabled:hover:bg-white disabled:cursor-not-allowed disabled:opacity-35"
              >
                {submitting ? (
                  <LoaderCircle className="size-4 animate-spin" />
                ) : (
                  <Check className="size-4" />
                )}
                {submitting ? "RECORDING REQUEST…" : "REQUEST DEPLOYMENT"}
              </button>

              {result ? (
                <div className="mt-5 rounded-2xl border border-white/[0.08] bg-[#020817]/65 p-5">
                  {result.detail || result.error ? (
                    <p className="text-sm text-red-200">
                      {result.detail || result.error}
                    </p>
                  ) : (
                    <>
                      <div className="text-sm font-semibold text-emerald-200">
                        Deployment request recorded
                      </div>
                      <p className="mt-2 text-xs leading-5 text-white/48">
                        Empire has recorded the company, requested deployment and
                        desired outcome for qualification and scoping.
                      </p>
                      <div className="mt-3 text-[10px] text-white/30">
                        Prospect {result.prospect_id}
                      </div>
                    </>
                  )}
                </div>
              ) : null}

              <div className="mt-5 text-center text-[10px] leading-5 text-white/28">
                Founder-approved entry pricing · scope verified before binding
                terms · no revenue recognized from this request
              </div>
            </form>
          </section>
        </div>
      </div>

      <style jsx>{`
        .input {
          width: 100%;
          border-radius: 0.75rem;
          border: 1px solid rgba(255,255,255,.10);
          background: rgba(2,8,23,.70);
          padding: .875rem 1rem;
          color: white;
          font-size: .875rem;
          outline: none;
          transition: border-color .2s ease;
        }
        .input:focus {
          border-color: rgba(96,165,250,.5);
        }
      `}</style>
    </main>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-2 text-xs text-white/55">
      {label}
      {children}
    </label>
  );
}
