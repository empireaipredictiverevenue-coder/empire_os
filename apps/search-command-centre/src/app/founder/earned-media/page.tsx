import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getFounderEarnedMedia, type EarnedMediaReviewItem } from "@/lib/founder-api";

const LANES: Array<{ key: EarnedMediaReviewItem["lane"]; label: string }> = [
  { key: "pr", label: "Press & PR" },
  { key: "editorial", label: "Editorial & organic" },
  { key: "consultancy", label: "Consultancy" },
  { key: "proposal", label: "Proposals" },
];

function humanState(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function startingPrice(item: EarnedMediaReviewItem) {
  if (typeof item.amount_minor !== "number") return null;
  return new Intl.NumberFormat("en-GB", {
    style: "currency", currency: "GBP", maximumFractionDigits: 0,
  }).format(item.amount_minor / 100)
    + (item.billing_model === "monthly" ? "/month" : " starting price");
}

export default async function FounderEarnedMediaPage() {
  // Feature flags are not authentication. Never release without verified ingress.
  if (process.env.EMPIRE_EARNED_MEDIA_FOUNDER_UI_ENABLED !== "1" ||
      process.env.EMPIRE_FOUNDER_CONSOLE_PRIVATE_AUTH_VERIFIED !== "1") {
    notFound();
  }
  await connection();
  const result = await getFounderEarnedMedia();
  const packet = result.data;
  const items = packet?.items ?? [];

  return (
    <main className="min-h-screen bg-[#060b18] px-4 py-7 text-slate-100 sm:px-6 lg:px-10">
      <div className="mx-auto max-w-[1450px]">
        <header className="rounded-3xl border border-white/10 bg-[#0b1225] p-6">
          <Link href="/founder" className="text-xs uppercase tracking-[0.16em] text-cyan-300">
            ← Founder Console
          </Link>
          <p className="mt-6 text-xs uppercase tracking-wider text-amber-300">
            Founder review only · no outbound authority
          </p>
          <h1 className="mt-2 text-3xl font-semibold">
            PR, Editorial, Consultancy & Proposals
          </h1>
          <p className="mt-3 max-w-4xl text-sm leading-6 text-slate-300">
            One evidence view across existing Marketing, Search and commercial work.
            Previous sent pitches are not new leads. Contract, publishing, CRM binding,
            accepted payment and attribution all require separate proof.
          </p>
          {!result.ok || !packet ? (
            <p className="mt-4 rounded-xl border border-amber-400/20 p-3 text-sm text-amber-200">
              Founder review unavailable ({result.reason ?? "read not configured"}).
              No authorisations inferred.
            </p>
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              {LANES.map((lane) => (
                <div key={lane.key} className="rounded-xl border border-white/10 bg-white/[0.035] p-4">
                  <p className="text-xs text-slate-400">{lane.label}</p>
                  <p className="mt-1 text-2xl font-semibold">{packet.lane_counts?.[lane.key] ?? 0}</p>
                </div>
              ))}
            </div>
          )}
        </header>
        {packet && (
          <>
            <div className="mt-5 rounded-2xl border border-amber-400/20 bg-amber-400/5 p-4 text-sm text-amber-100">
              <strong>Release:</strong> {humanState(packet.status ?? "unverified")}.
              CRM: {humanState(packet.crm_reconciliation_state ?? "unverified")}.
              No client deal or realised revenue is proved by these files.
            </div>
            {LANES.map((lane) => {
              const rows = items.filter((item) => item.lane === lane.key);
              return (
                <section key={lane.key} className="mt-7">
                  <h2 className="mb-3 text-xl font-semibold">{lane.label}</h2>
                  <div className="grid gap-3 md:grid-cols-2">
                    {rows.map((item) => (
                      <article key={item.item_id}
                        className="rounded-2xl border border-white/10 bg-[#0b1225] p-5">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <h3 className="text-lg font-medium">{item.label}</h3>
                          <span className="rounded-full border border-amber-400/25 px-3 py-1 text-xs text-amber-200">
                            {humanState(item.state)}
                          </span>
                        </div>
                        {startingPrice(item) &&
                          <p className="mt-2 text-sm text-cyan-200">{startingPrice(item)}</p>}
                        <p className="mt-3 text-sm leading-6 text-slate-300">{item.next_review}</p>
                        <p className="mt-3 break-all text-xs text-slate-500">
                          Evidence: {item.evidence_reference}
                        </p>
                        <p className="mt-2 text-xs text-slate-400">
                          Smart CRM: {humanState(item.crm_linkage?.state ?? "unverified")}
                        </p>
                      </article>
                    ))}
                  </div>
                </section>
              );
            })}
            {Object.values(packet.sources ?? {}).some((source) =>
              source.state.startsWith("HELD")
            ) && (
              <p className="mt-6 rounded-2xl border border-rose-400/30 p-4 text-sm text-rose-200">
                A source is missing or failed validation. Corresponding items remain held.
              </p>
            )}
            <p className="mt-10 text-xs text-slate-500">
              Historical, read-only Founder view. No send, publish, quote, contract,
              CRM write or payment controls.
            </p>
          </>
        )}
      </div>
    </main>
  );
}
