import Link from "next/link";
import { connection } from "next/server";
import {
  getFounderOutboundDeliverability,
  type DeliverabilityDomainSnapshot,
  type DeliverabilityWindow,
} from "@/lib/founder-api";


function pct(value?: number | null, digits = 2) {
  if (value == null || !Number.isFinite(value)) return "Unknown";
  return `${(value * 100).toFixed(digits)}%`;
}

function count(value?: number | null) {
  return value == null ? "—" : value.toLocaleString("en-GB");
}

function healthTone(value?: string | null) {
  switch ((value ?? "").toUpperCase()) {
    case "GREEN":
    case "READY":
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-100";
    case "AMBER":
    case "LIMITED":
    case "REMEDIATE":
      return "border-amber-400/30 bg-amber-400/10 text-amber-100";
    case "HOLD":
    case "RED":
      return "border-rose-400/35 bg-rose-400/10 text-rose-100";
    default:
      return "border-slate-400/20 bg-white/[0.04] text-slate-300";
  }
}

function healthGlow(value?: string | null) {
  switch ((value ?? "").toUpperCase()) {
    case "GREEN":
    case "READY":
      return "shadow-[0_0_80px_rgba(52,211,153,0.08)]";
    case "AMBER":
    case "LIMITED":
    case "REMEDIATE":
      return "shadow-[0_0_80px_rgba(251,191,36,0.08)]";
    case "HOLD":
    case "RED":
      return "shadow-[0_0_90px_rgba(251,113,133,0.10)]";
    default:
      return "shadow-2xl shadow-black/30";
  }
}

function label(value?: string | null) {
  return (value ?? "Unknown").replaceAll("_", " ");
}

function Metric({
  title,
  value,
  note,
}: {
  title: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
        {title}
      </p>
      <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-white">
        {value}
      </p>
      {note ? (
        <p className="mt-2 text-xs leading-5 text-slate-500">{note}</p>
      ) : null}
    </div>
  );
}

function WindowCard({
  name,
  window,
}: {
  name: string;
  window?: DeliverabilityWindow;
}) {
  if (!window) {
    return (
      <div className="rounded-3xl border border-white/10 bg-[#0b1328]/80 p-5">
        <p className="text-sm font-semibold text-slate-400">{name}</p>
        <p className="mt-3 text-sm text-slate-600">No evidence.</p>
      </div>
    );
  }

  return (
    <div
      className={[
        "rounded-3xl border border-white/10 bg-[#0b1328]/86 p-5",
        healthGlow(window.health),
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            Rolling window
          </p>
          <h2 className="mt-1 text-xl font-semibold text-white">{name}</h2>
        </div>
        <span
          className={[
            "rounded-full border px-3 py-1 text-xs font-semibold",
            healthTone(window.health),
          ].join(" ")}
        >
          {window.health ?? "UNKNOWN"}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3">
        <Metric title="Delivery" value={pct(window.delivery_rate)} />
        <Metric title="Bounce" value={pct(window.bounce_rate)} />
        <Metric title="Complaints" value={pct(window.complaint_rate, 3)} />
        <Metric title="Sent" value={count(window.sent)} />
      </div>

      {(window.hard_holds?.length ?? 0) > 0 ? (
        <div className="mt-4 rounded-2xl border border-rose-400/20 bg-rose-400/[0.06] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-rose-300">
            Hard holds
          </p>
          <p className="mt-2 text-xs leading-5 text-rose-100/80">
            {window.hard_holds?.map(label).join(" · ")}
          </p>
        </div>
      ) : null}

      {(window.warnings?.length ?? 0) > 0 ? (
        <div className="mt-3 rounded-2xl border border-amber-400/15 bg-amber-400/[0.045] p-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-amber-300">
            Warnings
          </p>
          <p className="mt-2 text-xs leading-5 text-amber-100/75">
            {window.warnings?.map(label).join(" · ")}
          </p>
        </div>
      ) : null}
    </div>
  );
}

function domainRows(
  windows?: Record<string, DeliverabilityWindow>,
): Array<[string, DeliverabilityDomainSnapshot]> {
  const preferred = windows?.["30d"] ?? windows?.["7d"] ?? windows?.["1d"];
  return Object.entries(preferred?.domains ?? {}).sort(
    (a, b) => (b[1].sent ?? 0) - (a[1].sent ?? 0),
  );
}

export default async function FounderDeliverabilityPage() {
  await connection();
  const result = await getFounderOutboundDeliverability();
  const data = result.data;
  const windows = data?.windows ?? {};
  const domains = domainRows(windows);
  const canonical = data?.canonical_evidence_store;
  const latestDecision = canonical?.latest_decision;
  const alert = data?.founder_alert;

  return (
    <main className="min-h-screen bg-[#050914] text-slate-100">
      <div className="fixed inset-0 -z-0 bg-[radial-gradient(circle_at_15%_0%,rgba(37,99,235,0.17),transparent_30%),radial-gradient(circle_at_88%_4%,rgba(14,165,233,0.09),transparent_27%),radial-gradient(circle_at_50%_100%,rgba(15,23,42,0.9),transparent_45%)]" />

      <div className="relative z-10 mx-auto max-w-[1680px] px-4 py-6 sm:px-6 lg:px-8">
        <header className="rounded-[32px] border border-white/10 bg-[#091124]/90 p-6 shadow-2xl shadow-black/40 backdrop-blur-xl lg:p-8">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <Link
                href="/founder"
                className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300 hover:text-cyan-200"
              >
                ← Founder Console
              </Link>
              <p className="mt-5 text-[11px] font-semibold uppercase tracking-[0.22em] text-slate-500">
                Ringleader · reputation command centre
              </p>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.05em] text-white sm:text-5xl">
                Outbound Deliverability
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-400">
                Empire-owned sender health, provider evidence and canonical
                reputation history. Delivery acceptance is never presented as
                proof of inbox placement.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <span
                className={[
                  "rounded-full border px-4 py-2 text-sm font-semibold",
                  healthTone(data?.overall_health),
                ].join(" ")}
              >
                {data?.overall_health ?? "UNKNOWN"}
              </span>
              <span className="rounded-full border border-blue-400/20 bg-blue-400/10 px-4 py-2 text-sm font-semibold text-blue-100">
                OBSERVE · read only
              </span>
            </div>
          </div>
        </header>

        {!result.ok || !data ? (
          <section className="mt-5 rounded-3xl border border-amber-400/20 bg-amber-400/[0.05] p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-300">
              Deliverability evidence unavailable
            </p>
            <h2 className="mt-2 text-xl font-semibold text-white">
              Ringleader could not reach the read API.
            </h2>
            <p className="mt-3 text-sm text-slate-400">
              {result.reason ?? "Provider evidence is currently unavailable."}
            </p>
          </section>
        ) : (
          <>
            {alert ? (
              <section
                className={[
                  "mt-5 rounded-3xl border p-5",
                  alert.severity === "CRITICAL"
                    ? "border-rose-400/25 bg-rose-400/[0.065]"
                    : "border-amber-400/20 bg-amber-400/[0.05]",
                ].join(" ")}
              >
                <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                      Founder alert · {alert.severity ?? "NOTICE"}
                    </p>
                    <h2 className="mt-2 text-xl font-semibold text-white">
                      Ringleader posture: {alert.posture ?? data.overall_health}
                    </h2>
                    <p className="mt-2 text-sm text-slate-400">
                      {(alert.hard_holds ?? []).length
                        ? alert.hard_holds?.map(label).join(" · ")
                        : "Health requires attention before capacity is increased."}
                    </p>
                  </div>
                  <span className="rounded-full border border-white/10 bg-black/15 px-3 py-1.5 text-[11px] font-medium text-slate-400">
                    {alert.fingerprint ?? "No fingerprint"}
                  </span>
                </div>
              </section>
            ) : null}

            <section className="mt-5 grid gap-4 xl:grid-cols-3">
              <WindowCard name="24 hours" window={windows["1d"]} />
              <WindowCard name="7 days" window={windows["7d"]} />
              <WindowCard name="30 days" window={windows["30d"]} />
            </section>

            <section className="mt-5 grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
              <div className="rounded-3xl border border-white/10 bg-[#091124]/88 p-5 shadow-xl shadow-black/20">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                      Domain estate
                    </p>
                    <h2 className="mt-1 text-xl font-semibold text-white">
                      Reputation by sending domain
                    </h2>
                  </div>
                  <p className="text-xs text-slate-500">
                    Highest-volume available window
                  </p>
                </div>

                <div className="mt-5 overflow-x-auto">
                  <table className="w-full min-w-[720px] text-left text-sm">
                    <thead>
                      <tr className="border-b border-white/10 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                        <th className="pb-3 font-semibold">Domain</th>
                        <th className="pb-3 font-semibold">Sent</th>
                        <th className="pb-3 font-semibold">Delivered</th>
                        <th className="pb-3 font-semibold">Delivery</th>
                        <th className="pb-3 font-semibold">Bounce</th>
                        <th className="pb-3 font-semibold">Complaint</th>
                      </tr>
                    </thead>
                    <tbody>
                      {domains.length ? (
                        domains.map(([domain, row]) => (
                          <tr key={domain} className="border-b border-white/[0.055]">
                            <td className="py-4 font-medium text-white">{domain}</td>
                            <td className="py-4 tabular-nums text-slate-300">
                              {count(row.sent)}
                            </td>
                            <td className="py-4 tabular-nums text-slate-300">
                              {count(row.delivered)}
                            </td>
                            <td className="py-4 tabular-nums text-slate-300">
                              {pct(row.delivery_rate)}
                            </td>
                            <td className="py-4 tabular-nums text-slate-300">
                              {pct(row.bounce_rate)}
                            </td>
                            <td className="py-4 tabular-nums text-slate-300">
                              {pct(row.complaint_rate, 3)}
                            </td>
                          </tr>
                        ))
                      ) : (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-slate-500">
                            No domain-level evidence returned.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>

              <div className="space-y-5">
                <section className="rounded-3xl border border-white/10 bg-[#091124]/88 p-5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Canonical evidence
                  </p>
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <h2 className="text-xl font-semibold text-white">EmpireDB</h2>
                    <span
                      className={[
                        "rounded-full border px-3 py-1 text-xs font-semibold",
                        canonical?.configured
                          ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-100"
                          : "border-amber-400/25 bg-amber-400/10 text-amber-100",
                      ].join(" ")}
                    >
                      {canonical?.configured ? "Connected" : "Not activated"}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    {canonical?.configured
                      ? "Canonical reputation history and replay are available."
                      : "Live provider evidence is visible, but canonical EmpireDB persistence remains gated."}
                  </p>
                </section>

                <section className="rounded-3xl border border-white/10 bg-[#091124]/88 p-5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Last canonical decision
                  </p>
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <h2 className="text-xl font-semibold text-white">
                      {latestDecision?.posture ?? "No persisted decision"}
                    </h2>
                    {latestDecision?.posture ? (
                      <span
                        className={[
                          "rounded-full border px-3 py-1 text-xs font-semibold",
                          healthTone(latestDecision.posture),
                        ].join(" ")}
                      >
                        {latestDecision.posture}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-3 break-words text-xs leading-5 text-slate-500">
                    {latestDecision?.observed_at ??
                      "Migration/roles have not yet produced canonical history."}
                  </p>
                </section>

                <section className="rounded-3xl border border-cyan-400/15 bg-cyan-400/[0.045] p-5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-cyan-300">
                    Inbox placement
                  </p>
                  <h2 className="mt-2 text-xl font-semibold text-white">
                    Separate measurement required
                  </h2>
                  <p className="mt-3 text-sm leading-6 text-slate-400">
                    Provider “delivered” events prove acceptance, not Primary or
                    Inbox placement. Ringleader keeps seed-placement evidence as
                    a separate signal.
                  </p>
                </section>
              </div>
            </section>

            <section className="mt-5 rounded-3xl border border-white/10 bg-[#091124]/88 p-5">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                    Ringleader controls
                  </p>
                  <h2 className="mt-1 text-xl font-semibold text-white">
                    Reputation stays upstream of sending
                  </h2>
                </div>
                <Link
                  href="/founder/mail"
                  className="rounded-xl border border-blue-400/20 bg-blue-400/10 px-4 py-2 text-xs font-semibold text-blue-100 hover:bg-blue-400/15"
                >
                  Open Empire Mail →
                </Link>
              </div>

              <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <Metric
                  title="Provider source"
                  value={data.source ?? "Unknown"}
                  note="External providers are evidence adapters, not the control plane."
                />
                <Metric
                  title="Inbox measurement"
                  value={label(data.inbox_placement?.status)}
                  note={data.inbox_placement?.reason}
                />
                <Metric
                  title="Canonical history"
                  value={canonical?.configured ? "Active" : "Gated"}
                  note="EmpireDB activation remains a separate founder approval."
                />
                <Metric
                  title="Send authority"
                  value="Unchanged"
                  note="Ringleader observes and constrains; the Outbound Governor remains authoritative."
                />
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
