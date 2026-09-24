"use client";

import { ArrowLeft, Check, Copy, LoaderCircle, ShieldCheck } from "lucide-react";
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

const DEFAULT_CODES = [
  "competitor_search_gap",
  "search_opportunity_map",
  "technical_search_audit",
  "solar_opportunity_map_us",
];

function formatProductName(product: Product) {
  return product.product_name || product.product_code.replaceAll("_", " ");
}

export default function BuyPage() {
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
      .catch(() => setCatalogError("Checkout catalogue is temporarily unavailable."));
  }, []);

  const product = useMemo(
    () => catalog?.products.find((item) => item.product_code === selected) || null,
    [catalog, selected],
  );

  async function submit(event: React.FormEvent) {
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
      if (!response.ok) {
        setResult({ detail: body.detail || body.error || "Checkout failed." });
      } else {
        setResult(body);
      }
    } catch {
      setResult({ detail: "Checkout is temporarily unavailable." });
    } finally {
      setSubmitting(false);
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
          <a href="/" className="inline-flex items-center gap-2 text-xs font-semibold tracking-[0.12em] text-white/55 transition hover:text-white">
            <ArrowLeft className="size-4" />
            EMPIRE AI
          </a>
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/20 bg-emerald-400/[0.06] px-3 py-2 text-[9px] font-semibold tracking-[0.14em] text-emerald-200">
            <ShieldCheck className="size-3.5" />
            VERIFIED CATALOG
          </div>
        </div>

        <div className="grid gap-10 lg:grid-cols-[1.08fr_.92fr]">
          <section>
            <div className="mb-5 text-[10px] font-semibold tracking-[0.22em] text-[#60a5fa]">
              SELF-SERVE INTELLIGENCE
            </div>
            <h1 className="max-w-3xl text-5xl font-medium leading-[.95] tracking-[-.05em] md:text-7xl">
              Buy the intelligence.
              <span className="block bg-gradient-to-r from-[#bfdbfe] to-[#67e8f9] bg-clip-text text-transparent">
                Skip the sales call.
              </span>
            </h1>
            <p className="mt-6 max-w-2xl text-base leading-7 text-white/55">
              Fixed-price, evidence-backed intelligence delivered from EmpireOS.
              Choose a product, settle in USDT on BNB Smart Chain, and the fulfilment
              workflow starts automatically after verified payment.
            </p>

            <div className="mt-9 grid gap-3">
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
                  <LoaderCircle className="size-4 animate-spin" /> Loading live catalogue…
                </div>
              ) : null}
              {catalogError ? (
                <div className="rounded-2xl border border-red-400/20 bg-red-400/[0.05] p-5 text-sm text-red-200">
                  {catalogError}
                </div>
              ) : null}
            </div>
          </section>

          <section className="lg:pt-12">
            <form onSubmit={submit} className="rounded-3xl border border-white/[0.09] bg-[#07142f]/80 p-6 shadow-[0_30px_100px_rgba(0,0,0,.3)] backdrop-blur-xl md:p-8">
              <div className="mb-7">
                <div className="text-xs font-semibold tracking-[0.14em] text-white/45">
                  CHECKOUT
                </div>
                <div className="mt-2 flex items-end justify-between gap-4">
                  <div className="text-lg font-semibold">
                    {product ? formatProductName(product) : "Select a product"}
                  </div>
                  <div className="text-3xl font-semibold tracking-[-.04em] text-[#bfdbfe]">
                    {product?.amount_display || "—"}
                  </div>
                </div>
              </div>

              <div className="grid gap-4">
                <label className="grid gap-2 text-xs text-white/55">
                  Business
                  <input required value={businessName} onChange={(e) => setBusinessName(e.target.value)} className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50" placeholder="Example Ltd" />
                </label>
                <label className="grid gap-2 text-xs text-white/55">
                  Work email
                  <input required type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50" placeholder="you@company.com" />
                </label>
                <label className="grid gap-2 text-xs text-white/55">
                  Domain to analyse
                  <input required value={domain} onChange={(e) => setDomain(e.target.value)} className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 text-sm text-white outline-none transition focus:border-[#60a5fa]/50" placeholder="company.com" />
                </label>
                <label className="grid gap-2 text-xs text-white/55">
                  BSC payer wallet
                  <input required value={wallet} onChange={(e) => setWallet(e.target.value)} className="rounded-xl border border-white/10 bg-[#020817]/70 px-4 py-3.5 font-mono text-xs text-white outline-none transition focus:border-[#60a5fa]/50" placeholder="0x…" />
                </label>
              </div>

              <label className="mt-5 flex cursor-pointer items-start gap-3 text-xs leading-5 text-white/48">
                <input
                  type="checkbox"
                  checked={accepted}
                  onChange={(e) => setAccepted(e.target.checked)}
                  className="mt-1"
                />
                <span>
                  I accept the displayed fixed price and authorize Empire AI to
                  create the order and payment request for this product. Payment
                  is only treated as paid after on-chain verification.
                </span>
              </label>

              <button
                disabled={!product || !accepted || submitting}
                className="mt-7 inline-flex min-h-13 w-full items-center justify-center gap-2 rounded-xl bg-[#eaf2ff] px-5 text-xs font-bold tracking-[0.11em] text-[#07132c] transition enabled:hover:-translate-y-0.5 enabled:hover:bg-white disabled:cursor-not-allowed disabled:opacity-35"
              >
                {submitting ? <LoaderCircle className="size-4 animate-spin" /> : <Check className="size-4" />}
                {submitting ? "CREATING ORDER…" : "CREATE PAYMENT REQUEST"}
              </button>

              {result ? (
                <div className="mt-5 rounded-2xl border border-white/[0.08] bg-[#020817]/65 p-5">
                  {result.detail || result.error ? (
                    <p className="text-sm text-red-200">{result.detail || result.error}</p>
                  ) : result.payment_request_created ? (
                    <div>
                      <div className="text-sm font-semibold text-emerald-200">
                        Payment request created
                      </div>
                      <p className="mt-2 text-xs leading-5 text-white/48">
                        Send exactly <strong className="text-white">{result.amount_usdt} USDT</strong> on BNB Smart Chain from the wallet entered above.
                      </p>
                      <div className="mt-4 flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 p-3">
                        <code className="min-w-0 flex-1 break-all text-[10px] text-[#93c5fd]">
                          {result.treasury_address}
                        </code>
                        <button type="button" onClick={copyTreasury} className="rounded-lg border border-white/10 p-2 text-white/55 hover:text-white" aria-label="Copy treasury address">
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
                        Payment setup is awaiting the fixed-product payment gate.
                        No payment has been counted and no revenue has been recognized.
                      </p>
                      <div className="mt-3 text-[10px] text-white/30">
                        Order {result.order_id}
                      </div>
                    </div>
                  )}
                </div>
              ) : null}

              <div className="mt-5 text-center text-[10px] leading-5 text-white/28">
                USDT · BNB Smart Chain · verified settlement only
              </div>
            </form>
          </section>
        </div>
      </div>
    </main>
  );
}
