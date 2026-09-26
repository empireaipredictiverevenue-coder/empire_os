"use client";

import {
  ArrowLeft,
  Check,
  Copy,
  LoaderCircle,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

type Product = {
  product_code: string;
  product_name: string;
  amount_cents: number;
  amount_display: string;
  currency: string;
  binding_terms_ready: boolean;
};

type Catalog = {
  products: Product[];
  count: number;
  settlement: { asset: string; network: string; chain_id: number };
};

type OrderResult = {
  order_id?: string;
  payment_request_created?: boolean;
  payment_request_status?: string;
  payment_request_id?: string;
  treasury_address?: string;
  amount_usdt?: string;
  network?: string;
  chain_id?: number;
  detail?: string;
  error?: string;
};

type ExchangeTier = {
  product_code: string;
  name: string;
  buyer_segment: string;
  corridor_limit: number | null;
  lead_classes: string[];
  allocation_priority: string;
  territory_model: string;
  exclusivity_eligible: boolean;
  delivery_modes: string[];
  included_features: string[];
  monthly_price_cents: number;
  monthly_price_display: string;
  usage_discount_bps: number | null;
  pricing_state: string;
  binding_terms_ready: boolean;
};

type ExchangeCatalog = {
  products: ExchangeTier[];
  count: number;
  monthly_membership: boolean;
  usage_or_overage: boolean;
  pricing_binding: boolean;
};

type ExchangeResult = {
  decision?: string;
  candidate_id?: string;
  tier_code?: string;
  requested_corridor_key?: string;
  daily_capacity?: number;
  delivery_preference?: string;
  pricing_binding?: boolean;
  seat_activated?: boolean;
  detail?: string;
  error?: string;
};

const DEFAULT_CODES = [
  "competitor_search_gap",
  "search_opportunity_map",
  "technical_search_audit",
  "solar_opportunity_map_us",
];

function human(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatProductName(product: Product) {
  return product.product_name || human(product.product_code);
}

function corridorLabel(limit: number | null) {
  if (limit === null) return "Custom corridors";
  return limit === 1 ? "1 corridor" : `${limit} corridors`;
}

export default function BuyPage() {
  const [mode, setMode] = useState<"intelligence" | "exchange">("intelligence");

  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [selected, setSelected] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [domain, setDomain] = useState("");
  const [wallet, setWallet] = useState("");
  const [accepted, setAccepted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<OrderResult | null>(null);

  const [exchange, setExchange] = useState<ExchangeCatalog | null>(null);
  const [exchangeError, setExchangeError] = useState("");
  const [tierCode, setTierCode] = useState("");
  const [niche, setNiche] = useState("");
  const [territory, setTerritory] = useState("");
  const [dailyCapacity, setDailyCapacity] = useState("5");
  const [deliveryPreference, setDeliveryPreference] = useState("email");
  const [exclusivity, setExclusivity] = useState(false);
  const [exchangeSubmitting, setExchangeSubmitting] = useState(false);
  const [exchangeResult, setExchangeResult] = useState<ExchangeResult | null>(null);

  useEffect(() => {
    fetch("/v1/checkout/catalog")
      .then(async (response) => {
        if (!response.ok) throw new Error("catalog unavailable");
        return response.json();
      })
      .then((body: Catalog) => {
        const products = (body.products || []).filter((item) =>
          DEFAULT_CODES.includes(item.product_code),
        );
        setCatalog({ ...body, products });
        if (products.length) setSelected(products[0].product_code);
      })
      .catch(() =>
        setCatalogError("Checkout catalogue is temporarily unavailable."),
      );

    fetch("/v1/checkout/exchange/tiers")
      .then(async (response) => {
        if (!response.ok) throw new Error("exchange unavailable");
        return response.json();
      })
      .then((body: ExchangeCatalog) => {
        setExchange(body);
        if (body.products?.length) setTierCode(body.products[0].product_code);
      })
      .catch(() =>
        setExchangeError("Lead Exchange access is temporarily unavailable."),
      );
  }, []);

  const product = useMemo(
    () => catalog?.products.find((item) => item.product_code === selected) || null,
    [catalog, selected],
  );

  const tier = useMemo(
    () => exchange?.products.find((item) => item.product_code === tierCode) || null,
    [exchange, tierCode],
  );

  useEffect(() => {
    if (tier && !tier.exclusivity_eligible && exclusivity) {
      setExclusivity(false);
    }
  }, [tier, exclusivity]);

  async function submitProduct(event: React.FormEvent) {
    event.preventDefault();
    if (!product || submitting) return;
    setSubmitting(true);
    setResult(null);
    const idempotencyKey =
      globalThis.crypto?.randomUUID?.() ||
      `checkout-${Date.now()}-${Math.random().toString(16).slice(2)}`;

    try {
      const response = await fetch("/v1/checkout/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          product_code: product.product_code,
          business_name: businessName,
          email,
          target_domain: domain,
          payer_wallet: wallet,
          terms_accepted: accepted,
          idempotency_key: idempotencyKey,
        }),
      });
      const body = await response.json();
      setResult(
        response.ok
          ? body
          : { detail: body.detail || body.error || "Checkout failed." },
      );
    } catch {
      setResult({ detail: "Checkout is temporarily unavailable." });
    } finally {
      setSubmitting(false);
    }
  }

  async function submitExchange(event: React.FormEvent) {
    event.preventDefault();
    if (!tier || exchangeSubmitting) return;
    setExchangeSubmitting(true);
    setExchangeResult(null);

    try {
      const response = await fetch("/v1/checkout/exchange/interests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tier_code: tier.product_code,
          business_name: businessName,
          email,
          domain,
          niche,
          territory,
          daily_capacity: Number(dailyCapacity),
          delivery_preference: deliveryPreference,
          exclusivity_interest: exclusivity,
        }),
      });
      const body = await response.json();
      setExchangeResult(
        response.ok
          ? body
          : {
              detail:
                body.detail ||
                body.error ||
                "Lead Exchange request could not be recorded.",
            },
      );
    } catch {
      setExchangeResult({
        detail: "Lead Exchange request is temporarily unavailable.",
      });
    } finally {
      setExchangeSubmitting(false);
    }
  }

  async function copyTreasury() {
    if (result?.treasury_address) {
      await navigator.clipboard.writeText(result.treasury_address);
    }
  }

  return (
    <main className="min-h-screen bg-[#020817] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_80%_10%,rgba(37,99,235,.16),transparent_30%),radial-gradient(circle_at_20%_70%,rgba(6,182,212,.08),transparent_26%)]" />
      <div className="relative mx-auto max-w-6xl px-5 py-8 md:px-8 md:py-12">
        <div className="mb-10 flex items-center justify-between">
          <a
            href="/"
            className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-white/55 transition hover:text-white"
          >
            <ArrowLeft className="size-4" />
            EMPIRE AI
          </a>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2 text-[9px] font-semibold tracking-[0.14em] text-emerald-200">
            <ShieldCheck className="size-3.5" />
            GOVERNED COMMERCE
          </div>
        </div>

        <div className="mb-10">
          <div className="text-[10px] font-semibold tracking-[0.22em] text-[#60a5fa]">
            EMPIRE SELF-SERVE
          </div>
          <h1 className="mt-4 max-w-4xl text-5xl font-medium leading-[.95] tracking-[-.05em] md:text-7xl">
            Intelligence and demand.
            <span className="block bg-gradient-to-r from-[#bfdbfe] to-[#67e8f9] bg-clip-text text-transparent">
              One commercial portal.
            </span>
          </h1>
          <p className="mt-6 max-w-2xl text-base leading-7 text-white/55">
            Buy evidence-backed intelligence instantly or join the Empire Lead
            Exchange for recurring access to qualified inventory.
          </p>
        </div>

        <div className="mb-6 rounded-2xl border border-blue-300/15 bg-blue-300/[0.04] p-4 md:flex md:items-center md:justify-between">
          <div>
            <div className="text-[10px] font-semibold tracking-[0.16em] text-[#93c5fd]">ENTERPRISE</div>
            <div className="mt-1 text-sm text-white/70">Deploy Predictive Revenue across the business.</div>
          </div>
          <a href="/predictive-revenue" className="mt-3 inline-flex rounded-full border border-[#60a5fa]/35 bg-[#2563eb]/15 px-4 py-2.5 text-[9px] font-semibold tracking-[0.12em] text-[#dbeafe] transition hover:border-[#7dd3fc]/60 hover:text-white md:mt-0">
            DEPLOY PREDICTIVE REVENUE
          </a>
        </div>

        <div className="mb-8 inline-flex rounded-full border border-white/[0.08] bg-white/[0.025] p-1">
          <button
            type="button"
            onClick={() => setMode("intelligence")}
            className={
              "rounded-full px-5 py-3 text-[10px] font-semibold tracking-[0.12em] transition " +
              (mode === "intelligence"
                ? "bg-[#eaf2ff] text-[#07132c]"
                : "text-white/45 hover:text-white")
            }
          >
            BUY INTELLIGENCE
          </button>
          <button
            type="button"
            onClick={() => setMode("exchange")}
            className={
              "rounded-full px-5 py-3 text-[10px] font-semibold tracking-[0.12em] transition " +
              (mode === "exchange"
                ? "bg-[#eaf2ff] text-[#07132c]"
                : "text-white/45 hover:text-white")
            }
          >
            JOIN LEAD EXCHANGE
          </button>
        </div>

        {mode === "intelligence" ? (
          <div className="grid gap-10 lg:grid-cols-[1.08fr_.92fr]">
            <section>
              <div className="mb-5 text-[10px] font-semibold tracking-[0.22em] text-[#60a5fa]">
                FIXED-PRICE INTELLIGENCE
              </div>
              <h2 className="text-4xl font-medium tracking-[-.04em] md:text-5xl">
                Skip the sales call.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-white/50">
                Choose a verified product, settle in USDT on BNB Smart Chain,
                then EmpireOS starts the fulfilment workflow after verified
                payment.
              </p>

              <div className="mt-8 grid gap-3">
                {catalog?.products.map((item) => {
                  const active = item.product_code === selected;
                  return (
                    <button
                      key={item.product_code}
                      type="button"
                      onClick={() => {
                        setSelected(item.product_code);
                        setResult(null);
                      }}
                      className={
                        "flex items-center justify-between rounded-2xl border p-5 text-left transition " +
                        (active
                          ? "border-[#60a5fa]/45 bg-[#0b1f4b]/75 shadow-[0_0_40px_rgba(37,99,235,.12)]"
                          : "border-white/[0.08] bg-white/[0.025] hover:border-white/15")
                      }
                    >
                      <span>
                        <strong className="block text-sm font-semibold text-white">
                          {formatProductName(item)}
                        </strong>
                        <span className="mt-1.5 block text-xs text-white/38">
                          One-time · verified commercial terms
                        </span>
                      </span>
                      <span className="text-xl font-semibold tracking-[-.03em] text-[#dbeafe]">
                        {item.amount_display}
                      </span>
                    </button>
                  );
                })}
                {!catalog && !catalogError ? (
                  <div className="flex items-center gap-3 rounded-2xl border border-white/[0.08] p-5 text-sm text-white/45">
                    <LoaderCircle className="size-4 animate-spin" />
                    Loading live catalogue…
                  </div>
                ) : null}
                {catalogError ? (
                  <div className="rounded-2xl border border-red-400/20 bg-red-400/[0.05] p-5 text-sm text-red-200">
                    {catalogError}
                  </div>
                ) : null}
              </div>
            </section>

            <section className="lg:pt-8">
              <form
                onSubmit={submitProduct}
                className="rounded-3xl border border-white/[0.09] bg-[#07142f]/80 p-6 shadow-[0_30px_100px_rgba(0,0,0,.3)] backdrop-blur-xl md:p-8"
              >
                <div className="mb-7 flex items-end justify-between gap-4">
                  <div>
                    <div className="text-xs font-semibold tracking-[0.14em] text-white/45">
                      CHECKOUT
                    </div>
                    <div className="mt-2 text-lg font-semibold">
                      {product ? formatProductName(product) : "Select a product"}
                    </div>
                  </div>
                  <div className="text-3xl font-semibold tracking-[-.04em] text-[#bfdbfe]">
                    {product?.amount_display || "—"}
                  </div>
                </div>

                <SharedIdentityFields
                  businessName={businessName}
                  setBusinessName={setBusinessName}
                  email={email}
                  setEmail={setEmail}
                  domain={domain}
                  setDomain={setDomain}
                />

                <label className="mt-4 grid gap-2 text-xs text-white/55">
                  BSC payer wallet
                  <input
                    required
                    value={wallet}
                    onChange={(event) => setWallet(event.target.value)}
                    className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 font-mono text-xs text-white outline-none transition focus:border-[#60a5fa]/50"
                    placeholder="0x…"
                  />
                </label>

                <label className="mt-5 flex cursor-pointer items-start gap-3 text-xs leading-5 text-white/48">
                  <input
                    type="checkbox"
                    checked={accepted}
                    onChange={(event) => setAccepted(event.target.checked)}
                    className="mt-1"
                  />
                  <span>
                    I accept the displayed fixed price and authorize Empire AI
                    to create the order and payment request. Payment is only
                    treated as paid after on-chain verification.
                  </span>
                </label>

                <button
                  disabled={!product || !accepted || submitting}
                  className="mt-7 inline-flex min-h-13 w-full items-center justify-center gap-2 rounded-xl bg-[#eaf2ff] px-5 text-xs font-bold tracking-[0.11em] text-[#07132c] transition enabled:hover:-translate-y-0.5 enabled:hover:bg-white disabled:cursor-not-allowed disabled:opacity-35"
                >
                  {submitting ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Check className="size-4" />
                  )}
                  {submitting
                    ? "CREATING ORDER…"
                    : "CREATE PAYMENT REQUEST"}
                </button>

                {result ? (
                  <ProductResult result={result} copyTreasury={copyTreasury} />
                ) : null}

                <div className="mt-5 text-center text-[10px] leading-5 text-white/28">
                  USDT · BNB Smart Chain · verified settlement only
                </div>
              </form>
            </section>
          </div>
        ) : (
          <div className="grid gap-10 lg:grid-cols-[1.12fr_.88fr]">
            <section>
              <div className="mb-5 text-[10px] font-semibold tracking-[0.22em] text-[#60a5fa]">
                COMMERCIAL EXCHANGE
              </div>
              <h2 className="max-w-3xl text-4xl font-medium tracking-[-.04em] md:text-5xl">
                Monthly access to the lead supply.
              </h2>
              <p className="mt-4 max-w-2xl text-sm leading-7 text-white/50">
                Your Exchange Seat controls corridor access, lead classes,
                allocation priority and territory options. Lead usage and
                overage sit on top of the monthly membership.
              </p>

              <div className="mt-8 grid gap-3 md:grid-cols-2">
                {exchange?.products.map((item) => {
                  const active = item.product_code === tierCode;
                  return (
                    <button
                      key={item.product_code}
                      type="button"
                      onClick={() => {
                        setTierCode(item.product_code);
                        setExchangeResult(null);
                      }}
                      className={
                        "rounded-2xl border p-5 text-left transition " +
                        (active
                          ? "border-emerald-300/35 bg-emerald-300/[0.06] shadow-[0_0_35px_rgba(16,185,129,.08)]"
                          : "border-white/[0.08] bg-white/[0.025] hover:border-white/15")
                      }
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <strong className="block text-sm font-semibold text-white">
                            {item.name.replace("Commercial Exchange ", "")}
                          </strong>
                          <span className="mt-1.5 block text-xs text-white/38">
                            {corridorLabel(item.corridor_limit)}
                          </span>
                        </div>
                        <Zap className="size-4 text-emerald-200/70" />
                      </div>

                      <div className="mt-4 flex flex-wrap gap-1.5">
                        {item.lead_classes.map((leadClass) => (
                          <span
                            key={leadClass}
                            className="rounded-full border border-white/[0.08] bg-white/[0.03] px-2.5 py-1 text-[9px] text-white/45"
                          >
                            {human(leadClass)}
                          </span>
                        ))}
                      </div>

                      <div className="mt-4 text-[10px] leading-5 text-white/35">
                        {human(item.allocation_priority)} allocation
                        {item.exclusivity_eligible
                          ? " · exclusivity eligible"
                          : ""}
                      </div>
                      <div className="mt-3 flex items-end justify-between gap-3">
                        <div className="text-sm font-semibold text-[#bfdbfe]">
                          {item.monthly_price_display}
                        </div>
                        <div className="text-[9px] text-white/32">
                          {item.usage_discount_bps === null
                            ? "Custom usage"
                            : item.usage_discount_bps > 0
                              ? `${item.usage_discount_bps / 100}% usage discount`
                              : "Standard usage"}
                        </div>
                      </div>
                    </button>
                  );
                })}

                {!exchange && !exchangeError ? (
                  <div className="flex items-center gap-3 rounded-2xl border border-white/[0.08] p-5 text-sm text-white/45">
                    <LoaderCircle className="size-4 animate-spin" />
                    Loading Exchange seats…
                  </div>
                ) : null}
                {exchangeError ? (
                  <div className="rounded-2xl border border-red-400/20 bg-red-400/[0.05] p-5 text-sm text-red-200">
                    {exchangeError}
                  </div>
                ) : null}
              </div>
            </section>

            <section className="lg:pt-8">
              <form
                onSubmit={submitExchange}
                className="rounded-3xl border border-white/[0.09] bg-[#07142f]/80 p-6 shadow-[0_30px_100px_rgba(0,0,0,.3)] backdrop-blur-xl md:p-8"
              >
                <div className="mb-6">
                  <div className="text-xs font-semibold tracking-[0.14em] text-white/45">
                    JOIN LEAD EXCHANGE
                  </div>
                  <div className="mt-2 text-lg font-semibold">
                    {tier
                      ? tier.name.replace("Commercial Exchange ", "")
                      : "Select a seat"}
                  </div>
                  <p className="mt-2 text-xs leading-5 text-white/38">
                    Tell Empire what you buy. This records your requested
                    market and capacity; it does not activate a seat or charge
                    you until the membership terms are confirmed.
                  </p>
                </div>

                <SharedIdentityFields
                  businessName={businessName}
                  setBusinessName={setBusinessName}
                  email={email}
                  setEmail={setEmail}
                  domain={domain}
                  setDomain={setDomain}
                />

                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <label className="grid gap-2 text-xs text-white/55">
                    Lead vertical
                    <input
                      required
                      value={niche}
                      onChange={(event) => setNiche(event.target.value)}
                      className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
                      placeholder="Roofing, Solar, HVAC…"
                    />
                  </label>
                  <label className="grid gap-2 text-xs text-white/55">
                    Territory
                    <input
                      required
                      value={territory}
                      onChange={(event) => setTerritory(event.target.value)}
                      className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
                      placeholder="Greater Manchester"
                    />
                  </label>
                  <label className="grid gap-2 text-xs text-white/55">
                    Leads you can take / day
                    <input
                      required
                      type="number"
                      min={1}
                      max={10000}
                      value={dailyCapacity}
                      onChange={(event) => setDailyCapacity(event.target.value)}
                      className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
                    />
                  </label>
                  <label className="grid gap-2 text-xs text-white/55">
                    Delivery
                    <select
                      value={deliveryPreference}
                      onChange={(event) =>
                        setDeliveryPreference(event.target.value)
                      }
                      className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
                    >
                      <option value="email">Email</option>
                      <option value="webhook">Webhook</option>
                      <option value="api">API</option>
                      <option value="phone">Phone</option>
                    </select>
                  </label>
                </div>

                {tier?.exclusivity_eligible ? (
                  <label className="mt-5 flex cursor-pointer items-start gap-3 text-xs leading-5 text-white/48">
                    <input
                      type="checkbox"
                      checked={exclusivity}
                      onChange={(event) => setExclusivity(event.target.checked)}
                      className="mt-1"
                    />
                    <span>
                      I’m interested in territory exclusivity where available.
                    </span>
                  </label>
                ) : null}

                <button
                  disabled={!tier || exchangeSubmitting}
                  className="mt-7 inline-flex min-h-13 w-full items-center justify-center gap-2 rounded-xl bg-emerald-100 px-5 text-xs font-bold tracking-[0.11em] text-[#052318] transition enabled:hover:-translate-y-0.5 enabled:hover:bg-white disabled:cursor-not-allowed disabled:opacity-35"
                >
                  {exchangeSubmitting ? (
                    <LoaderCircle className="size-4 animate-spin" />
                  ) : (
                    <Zap className="size-4" />
                  )}
                  {exchangeSubmitting
                    ? "RECORDING REQUEST…"
                    : "REQUEST EXCHANGE SEAT"}
                </button>

                {exchangeResult ? (
                  <div className="mt-5 rounded-2xl border border-white/[0.08] bg-[#020817]/65 p-5">
                    {exchangeResult.detail || exchangeResult.error ? (
                      <p className="text-sm text-red-200">
                        {exchangeResult.detail || exchangeResult.error}
                      </p>
                    ) : (
                      <>
                        <div className="text-sm font-semibold text-emerald-200">
                          Exchange request recorded
                        </div>
                        <p className="mt-2 text-xs leading-5 text-white/48">
                          Empire now has your requested market, capacity and
                          delivery route. No seat has been activated and no
                          payment has been taken yet.
                        </p>
                        <div className="mt-3 text-[10px] text-white/30">
                          Request {exchangeResult.candidate_id}
                        </div>
                      </>
                    )}
                  </div>
                ) : null}

                <div className="mt-5 text-center text-[10px] leading-5 text-white/28">
                  Founder-approved membership pricing + usage/overage · seat
                  activation still requires verified commercial terms
                </div>
              </form>
            </section>
          </div>
        )}
      </div>
    </main>
  );
}

function SharedIdentityFields({
  businessName,
  setBusinessName,
  email,
  setEmail,
  domain,
  setDomain,
}: {
  businessName: string;
  setBusinessName: (value: string) => void;
  email: string;
  setEmail: (value: string) => void;
  domain: string;
  setDomain: (value: string) => void;
}) {
  return (
    <div className="grid gap-4">
      <label className="grid gap-2 text-xs text-white/55">
        Business
        <input
          required
          value={businessName}
          onChange={(event) => setBusinessName(event.target.value)}
          className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
          placeholder="Example Ltd"
        />
      </label>
      <label className="grid gap-2 text-xs text-white/55">
        Work email
        <input
          required
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
          placeholder="you@company.com"
        />
      </label>
      <label className="grid gap-2 text-xs text-white/55">
        Company domain
        <input
          required
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50"
          placeholder="company.com"
        />
      </label>
    </div>
  );
}

function ProductResult({
  result,
  copyTreasury,
}: {
  result: OrderResult;
  copyTreasury: () => Promise<void>;
}) {
  return (
    <div className="mt-5 rounded-2xl border border-white/[0.08] bg-[#020817]/65 p-5">
      {result.detail || result.error ? (
        <p className="text-sm text-red-200">
          {result.detail || result.error}
        </p>
      ) : result.payment_request_created ? (
        <div>
          <div className="text-sm font-semibold text-emerald-200">
            Payment request created
          </div>
          <p className="mt-2 text-xs leading-5 text-white/48">
            Send exactly{" "}
            <strong className="text-white">{result.amount_usdt} USDT</strong>{" "}
            on BNB Smart Chain from the wallet entered above.
          </p>
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 p-3">
            <code className="min-w-0 flex-1 break-all text-[10px] text-[#93c5fd]">
              {result.treasury_address}
            </code>
            <button
              type="button"
              onClick={copyTreasury}
              className="rounded-lg border border-white/10 p-2 text-white/55 hover:text-white"
              aria-label="Copy treasury address"
            >
              <Copy className="size-3.5" />
            </button>
          </div>
          <div className="mt-3 text-[10px] text-white/30">
            Order {result.order_id}
          </div>
        </div>
      ) : (
        <div>
          <div className="text-sm font-semibold text-[#bfdbfe]">
            Order created
          </div>
          <p className="mt-2 text-xs leading-5 text-white/48">
            The order is recorded. No payment has been counted and no revenue
            has been recognized.
          </p>
          <div className="mt-3 text-[10px] text-white/30">
            Order {result.order_id}
          </div>
        </div>
      )}
    </div>
  );
}
