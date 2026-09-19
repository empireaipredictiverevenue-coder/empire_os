import Link from "next/link";
import { connection } from "next/server";
import {
  type ApiResult,
  type CollectionEnvelope,
  getDashboardData,
} from "@/lib/search-api";

function formatMoney(value: unknown) {
  if (typeof value !== "number") return "—";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value / 100);
}

function formatMetric(value: unknown) {
  return typeof value === "number"
    ? new Intl.NumberFormat("en-GB").format(value)
    : "—";
}

function StatusPill({
  good,
  children,
}: {
  good: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={[
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-semibold tracking-wide",
        good
          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
          : "border-amber-400/30 bg-amber-400/10 text-amber-200",
      ].join(" ")}
    >
      <span
        className={[
          "h-1.5 w-1.5 rounded-full",
          good ? "bg-emerald-300" : "bg-amber-300",
        ].join(" ")}
      />
      {children}
    </span>
  );
}

function GateState({ reason }: { reason?: string }) {
  const message =
    reason === "canonical_search_repository_not_activated"
      ? "Canonical reader is ready, but production activation is still gated."
      : reason === "api_base_not_configured"
        ? "Server-only Search API binding has not been configured."
        : reason === "api_unreachable"
          ? "Empire Search API is currently unreachable."
          : "This evidence surface is not available yet.";

  return (
    <div className="mt-7 rounded-2xl border border-dashed border-white/10 bg-black/20 p-5">
      <p className="text-sm font-medium text-slate-300">{message}</p>
      <p className="mt-2 font-mono text-[11px] uppercase tracking-wider text-slate-600">
        {reason ?? "unknown_gate"}
      </p>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
  accent = false,
}: {
  label: string;
  value: string;
  detail: string;
  accent?: boolean;
}) {
  return (
    <div className={accent ? "metric-card metric-accent" : "metric-card"}>
      <p className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
        {label}
      </p>
      <p className="mt-4 text-3xl font-semibold tracking-tight text-white">
        {value}
      </p>
      <p className="mt-2 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

function ReadinessItem({
  label,
  state,
  good,
}: {
  label: string;
  state: string;
  good: boolean;
}) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <div className="mt-3 flex items-center gap-2 text-sm font-medium text-slate-200">
        <span className={good ? "h-2 w-2 rounded-full bg-emerald-300" : "h-2 w-2 rounded-full bg-amber-300"} />
        {state}
      </div>
    </div>
  );
}

function primaryLabel(item: Record<string, unknown>, index: number) {
  return String(
    item.title ??
      item.query ??
      item.url ??
      item.alert_type ??
      item.attribution_kind ??
      "Record " + (index + 1),
  );
}

function secondaryLabel(item: Record<string, unknown>) {
  return String(
    item.topic ??
      item.state ??
      item.severity ??
      item.score_reason ??
      item.source ??
      "Observed canonical record",
  );
}

function CollectionPanel({
  title,
  result,
  emptyLabel,
}: {
  title: string;
  result: ApiResult<CollectionEnvelope>;
  emptyLabel: string;
}) {
  return (
    <section className="panel min-h-64">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Canonical feed</p>
          <h2 className="mt-1 text-lg font-semibold text-white">{title}</h2>
        </div>
        <StatusPill good={result.ok}>
          {result.ok ? "LIVE READ" : "GATED"}
        </StatusPill>
      </div>

      {!result.ok ? (
        <GateState reason={result.reason} />
      ) : result.data?.items.length ? (
        <div className="mt-4 divide-y divide-white/8">
          {result.data.items.slice(0, 5).map((item, index) => (
            <div
              className="grid gap-2 py-4 text-sm md:grid-cols-[1fr_auto]"
              key={title + "-" + index}
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-white">
                  {primaryLabel(item, index)}
                </p>
                <p className="mt-1 truncate text-xs text-slate-500">
                  {secondaryLabel(item)}
                </p>
              </div>
              <div className="text-xs font-medium text-slate-400">
                {typeof item.opportunity_score === "number"
                  ? Math.round(item.opportunity_score * 100) + " score"
                  : typeof item.revenue_cents === "number"
                    ? formatMoney(item.revenue_cents)
                    : ""}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-10 text-sm text-slate-500">{emptyLabel}</p>
      )}
    </section>
  );
}

export default async function Home() {
  await connection();
  const data = await getDashboardData();

  const health = data.health.data;
  const metrics =
    data.summary.ok &&
    data.summary.data &&
    typeof data.summary.data.stored_metrics === "object"
      ? data.summary.data.stored_metrics
      : null;

  const apiConnected = data.health.ok;
  const repositoryReady = health?.repository_available === true;
  const observeMode =
    health?.execution_mode === "OBSERVE" ||
    health?.execution_mode === "observe";

  return (
    <main className="min-h-screen bg-[#07100d] text-slate-100">
      <div className="grid-noise" />
      <div className="mx-auto max-w-[1500px] px-5 py-6 lg:px-10 lg:py-9">
        <header className="border-b border-white/10 pb-7">
          <div className="flex flex-col justify-between gap-6 xl:flex-row xl:items-end">
            <div>
              <div className="mb-5 flex items-center gap-3">
                <div className="brand-mark">E</div>
                <div>
                  <p className="text-sm font-semibold tracking-[0.22em] text-emerald-200">EMPIRE AI</p>
                  <p className="text-xs text-slate-500">Predictive Revenue Operating System</p>
                </div>
              </div>
              <p className="eyebrow">Phase 5 · Organic Growth Engine</p>
              <h1 className="mt-2 max-w-4xl text-4xl font-semibold tracking-[-0.04em] text-white md:text-6xl">
                Search Command Centre
              </h1>
              <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-400 md:text-base">
                Governed organic revenue intelligence. Real evidence only. Publishing, index submission and search mutations remain separately gated.
              </p>
              <div className="mt-5 flex flex-wrap gap-5">
                <Link
                  href="/technical"
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
                >
                  Technical intelligence →
                </Link>
                <Link
                  href="/competitors"
                  className="text-xs font-semibold uppercase tracking-[0.16em] text-emerald-300 hover:text-emerald-200"
                >
                  Competitor gaps →
                </Link>
              </div>
            </div>

            <div className="flex flex-wrap gap-2">
              <StatusPill good={apiConnected}>{apiConnected ? "API CONNECTED" : "API DISCONNECTED"}</StatusPill>
              <StatusPill good={repositoryReady}>{repositoryReady ? "REPOSITORY ACTIVE" : "REPOSITORY GATED"}</StatusPill>
              <StatusPill good={observeMode}>{observeMode ? "OBSERVE" : "MODE UNKNOWN"}</StatusPill>
            </div>
          </div>
        </header>

        <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <MetricCard label="Canonical pages" value={formatMetric(metrics?.pages)} detail="Search inventory" />
          <MetricCard label="Opportunities" value={formatMetric(metrics?.opportunities)} detail="Evidence-ranked" />
          <MetricCard label="Indexed" value={formatMetric(metrics?.indexed_pages)} detail="Observed state" />
          <MetricCard label="Open alerts" value={formatMetric(metrics?.open_alerts)} detail="Needs review" />
          <MetricCard label="Attributed revenue" value={formatMoney(metrics?.revenue_cents)} detail="Observed only" accent />
        </section>

        <section className="mt-4 grid gap-4 xl:grid-cols-[1.4fr_.6fr]">
          <div className="panel">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="eyebrow">Control plane</p>
                <h2 className="mt-1 text-lg font-semibold text-white">Search Intelligence readiness</h2>
              </div>
              <p className="font-mono text-xs text-slate-600">{String(health?.api_contract_version ?? "search-v1")}</p>
            </div>
            <div className="mt-6 grid gap-3 md:grid-cols-3">
              <ReadinessItem label="Content Quality Firewall" state="Ready" good />
              <ReadinessItem label="Canonical repository" state={repositoryReady ? "Active" : "Awaiting gate"} good={repositoryReady} />
              <ReadinessItem label="Mutation authority" state={health?.mutations_enabled === false ? "Disabled" : "Unknown"} good={health?.mutations_enabled === false} />
            </div>
          </div>

          <div className="panel">
            <p className="eyebrow">Google Search Console</p>
            <h2 className="mt-1 text-lg font-semibold text-white">Evidence connector</h2>
            {data.searchConsole.ok && data.searchConsole.data ? (
              <div className="mt-6">
                <StatusPill good={data.searchConsole.data.available}>{data.searchConsole.data.available ? "AVAILABLE" : "GATED"}</StatusPill>
                <p className="mt-4 text-sm text-slate-400">
                  {data.searchConsole.data.configured
                    ? "Credential binding detected; activation remains governed."
                    : "Disabled by default until approved credentials are bound."}
                </p>
                <p className="mt-3 font-mono text-[11px] text-slate-600">{data.searchConsole.data.reason}</p>
              </div>
            ) : (
              <GateState reason={data.searchConsole.reason} />
            )}
          </div>
        </section>

        <section className="mt-4 grid gap-4 lg:grid-cols-2">
          <CollectionPanel title="Top opportunities" result={data.opportunities} emptyLabel="No canonical opportunities observed." />
          <CollectionPanel title="Page intelligence" result={data.pages} emptyLabel="No canonical pages observed." />
          <CollectionPanel title="Search alerts" result={data.alerts} emptyLabel="No open search alerts observed." />
          <CollectionPanel title="Organic revenue evidence" result={data.revenue} emptyLabel="No search-attributed revenue observed." />
        </section>

        <footer className="mt-6 flex flex-col justify-between gap-3 border-t border-white/10 pt-5 text-xs text-slate-600 md:flex-row">
          <p>Empire Search Intelligence · recommendation-only surface</p>
          <p>No fabricated metrics · no automatic publish/index authority</p>
        </footer>
      </div>
    </main>
  );
}
