import Link from "next/link";
import { connection } from "next/server";
import { getPrimeDigitalTwinCockpit } from "@/lib/founder-api";

type Params = Promise<{ scenario?: string | string[]; depth?: string | string[] }>;
const single = (s?: string | string[]) => Array.isArray(s) ? s[0] : s;
const label = (s?: string | null) => (s ?? "Unknown").replaceAll("_", " ");
const integer = (n?: number) => typeof n === "number" ? n.toLocaleString("en-GB") : "Unknown";

export default async function PrimeTwinCockpit({ searchParams }: { searchParams: Params }) {
  await connection();
  const params = await searchParams;
  const id = single(params.scenario) ?? "pricing_resolution";
  const scenario = /^[a-z][a-z0-9_-]{1,55}$/.test(id) ? id : "pricing_resolution";
  const value = Number(single(params.depth) ?? "2");
  const depth = Number.isInteger(value) && value >= 0 && value <= 2 ? value : 2;
  const { ok, data, reason } = await getPrimeDigitalTwinCockpit(scenario, depth);
  const selected = data?.selected_scenario;
  const fractal = data?.selected_fractal;
  const baseline = data?.all_synthetic_baseline;
  const metrics = [
    ["Fictional scenarios", integer(baseline?.scripted_scenarios), "Existing synthetic research"],
    ["Fractal stress nodes", integer(baseline?.fractal_nodes_at_depth_two), "Bounded depth-two cases"],
    ["Expected safety holds", integer(baseline?.expected_safety_holds), "Deliberately blocked paths"],
    ["Verified real-world accuracy", "Unknown", "Requires genuine independent outcomes"],
  ];

  return <main className="min-h-screen bg-[#050b18] text-slate-100">
    <div className="mx-auto max-w-[1550px] px-5 py-8 lg:px-10 lg:py-12">
      <header className="border-b border-sky-200/10 pb-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Link href="/founder" className="text-xs uppercase tracking-widest text-sky-300 hover:text-sky-100">
            ← Founder Console
          </Link>
          <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-3 py-2 text-xs font-semibold text-amber-200">
            SYNTHETIC RESEARCH · NOT LIVE BUYER DATA
          </span>
        </div>
        <p className="mt-8 text-xs font-semibold uppercase tracking-[0.2em] text-amber-300">
          EMPIRE AI / ORIGINAL PREDICTIVE CLOUD / PRIME
        </p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-white md:text-6xl">
          Digital Twin Conversation Cockpit
        </h1>
        <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-300">
          Fictional buyer–seller dialogue, objection lifecycle, fractal branches and
          physics-inspired message-loss stress. None of this establishes genuine buyer
          intent, emotion accuracy, contracts, sales or recognised revenue.
        </p>
      </header>

      {!ok || !data ? <section className="mt-8 rounded-2xl border border-amber-400/30 bg-amber-400/[0.05] p-7">
        <h2 className="text-xl font-semibold text-white">Original Founder API unavailable</h2>
        <p className="mt-3 text-sm text-slate-300">{reason ?? "Unknown"}. This research page
          remains on HOLD until its original private access and ingress are approved.</p>
      </section> : <>
        <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map(([name, count, note]) => <div key={name}
            className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
            <p className="text-xs uppercase tracking-widest text-slate-400">{name}</p>
            <p className="mt-3 text-3xl font-semibold text-white">{count}</p>
            <p className="mt-2 text-xs text-slate-500">{note}</p>
          </div>)}
        </section>

        <section className="mt-6 rounded-2xl border border-sky-400/20 bg-sky-400/[0.035] p-6">
          <p className="text-xs uppercase tracking-widest text-sky-300">Read-only simulation controls</p>
          <h2 className="mt-2 text-2xl font-semibold">Rehearse one fictional scenario</h2>
          <p className="mt-2 text-sm text-slate-400">
            Refresh the deterministic simulation. This does not run the local model or send messages.
          </p>
          <form action="/founder/prime-digital-twin" method="get"
            className="mt-5 flex flex-col gap-3 md:flex-row md:items-end">
            <label className="flex-1 text-xs font-semibold text-slate-300">
              Scenario
              <select name="scenario" defaultValue={data.selected_scenario_id}
                className="mt-2 w-full rounded-xl border border-sky-200/20 bg-[#0b1830] px-4 py-3 text-sm text-white">
                {data.scenario_options.map(item => <option key={item.id} value={item.id}>
                  {item.name}
                </option>)}
              </select>
            </label>
            <label className="w-full text-xs font-semibold text-slate-300 md:w-48">
              Fractal depth
              <select name="depth" defaultValue={String(data.fractal_depth)}
                className="mt-2 w-full rounded-xl border border-sky-200/20 bg-[#0b1830] px-4 py-3 text-sm text-white">
                <option value="0">0 · Baseline</option>
                <option value="1">1 · Three nodes</option>
                <option value="2">2 · Seven nodes</option>
              </select>
            </label>
            <button type="submit" className="rounded-xl bg-sky-400 px-6 py-3 text-sm font-semibold text-[#061122] hover:bg-sky-300">
              Run fictional rehearsal
            </button>
          </form>
        </section>

        <div className="mt-6 grid gap-5 xl:grid-cols-2">
          <section className="rounded-2xl border border-white/10 bg-white/[0.025] p-6">
            <p className="text-xs uppercase tracking-widest text-sky-300">Conversation arena</p>
            <h2 className="mt-2 text-2xl font-semibold">Fictional buyer ↔ seller</h2>
            <p className="mt-3 text-sm text-slate-400">
              Concern: {label(selected?.original_objection_code)} ·
              Outcome: {label(selected?.outcome_state_not_provider_verified)}
            </p>
            <div className="mt-5 space-y-3">
              {(selected?.simulated_dialogue ?? []).map((turn, i) =>
                <div key={i} className={"rounded-2xl border p-4 " +
                  (turn.actor === "FICTIONAL_BUYER_TWIN"
                    ? "border-sky-400/20 bg-sky-400/[0.06]"
                    : "border-amber-300/20 bg-amber-300/[0.04]")}>
                  <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">
                    {turn.actor === "FICTIONAL_BUYER_TWIN" ? "Fictional buyer" : "Scripted seller"}
                  </p>
                  <p className="mt-2 text-sm leading-7 text-white">{turn.text}</p>
                </div>)}
            </div>
            <p className="mt-5 text-xs text-slate-400">Anti-loop watchdog:
              {label(selected?.loop_guard.status)}. No real conversations analysed.</p>
          </section>
          <section className="rounded-2xl border border-white/10 bg-white/[0.025] p-6">
            <p className="text-xs uppercase tracking-widest text-amber-300">Fractal + physics explorer</p>
            <h2 className="mt-2 text-2xl font-semibold">
              {integer(fractal?.total_nodes)} synthetic branches
            </h2>
            <p className="mt-3 text-sm text-slate-400">
              {integer(fractal?.safety_or_causal_holds)} expected causal/policy holds ·
              {integer(fractal?.loop_stalls)} loop stalls
            </p>
            <div className="mt-5 max-h-[560px] space-y-3 overflow-y-auto">
              {(fractal?.branches ?? []).map((branch, i) =>
                <div key={branch.path + i} className="rounded-xl border border-white/10 bg-[#0a1427] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-sm text-sky-200">{branch.path}</span>
                    <span className={branch.hold_reasons.length
                      ? "text-xs font-semibold text-amber-300"
                      : "text-xs font-semibold text-emerald-300"}>
                      {branch.hold_reasons.length ? "EXPECTED HOLD" : "CAUSAL IN SIMULATION"}
                    </span>
                  </div>
                  <p className="mt-2 text-xs text-slate-400">{branch.stress} ·
                    {branch.latency_ms} ms synthetic latency ·
                    {branch.dropped_messages} dropped · {label(branch.simulated_state)}
                  </p>
                  {!!branch.hold_reasons.length && <p className="mt-2 text-xs text-amber-200">
                    {branch.hold_reasons.map(label).join(" · ")}
                  </p>}
                </div>)}
            </div>
          </section>
        </div>
        <section className="mt-6 rounded-2xl border border-sky-400/20 bg-sky-400/[0.025] p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-sky-300">
            Original PRIME situation and capability map
          </p>
          <h2 className="mt-2 text-2xl font-semibold">What the assistant knows it cannot yet do</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Capability registry membership is a policy definition, not a working integration.
            All listed real-world actions remain unavailable from this research cockpit.
            Voice, reminders, calendar, devices, media and communications need separately
            verified providers, explicit permissions and original owner approval.
          </p>
          <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {(data.assistant_capability_map ?? []).map(item =>
              <div key={item.request_code}
                className="rounded-xl border border-white/10 bg-[#0a1427] px-4 py-3">
                <p className="text-sm font-semibold text-slate-100">
                  {label(item.request_code)}
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  {item.original_agi_capability_registered
                    ? "Existing policy registry · NOT a live feature"
                    : "Integration not registered/verified"}
                </p>
              </div>)}
          </div>
          <p className="mt-5 text-xs leading-6 text-amber-200">
            Current situational review: {label(data.situational_awareness.status)}.
            No claim of subjective consciousness, universal situational knowledge
            or independent source authentication.
          </p>
        </section>
        <section className="mt-6 rounded-2xl border border-sky-400/15 bg-sky-400/[0.025] p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-sky-300">
            Original EmpireDB timer recovery
          </p>
          <h2 className="mt-2 text-2xl font-semibold">Durable scheduling evidence gate</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Recovery state: {label(data.original_timer_recovery.status)}.
            Event ordering, cancellation, crash reconciliation and reported delivery
            have a tested synthetic contract. The candidate EmpireDB schema is held,
            no live scheduler or notification service is connected, and a provider
            acceptance must never be displayed as a delivered reminder.
          </p>
          <p className="mt-3 text-xs text-amber-200">
            Actual user notification verified: No · Original production DB changed: No
          </p>
        </section>
        <section className="mt-6 rounded-2xl border border-amber-300/20 bg-amber-300/[0.025] p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-amber-300">
            Original PRIME notification evidence
          </p>
          <h2 className="mt-2 text-2xl font-semibold">Delivery and reconciliation</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Provider receipt integration: {label(data.provider_receipt_reconciliation.status)}.
            Synthetic provider receipt validation can examine a claim, acceptance,
            reported device delivery, failure or missing response without automatically
            resending an ambiguous notification.
          </p>
          <p className="mt-3 text-xs leading-6 text-amber-200">
            Real provider delivery verified: No · User device receipt verified: No ·
            Automatic resend: Disabled · Provider integration: Not connected
          </p>
        </section>
        <section className="mt-6 rounded-2xl border border-sky-400/20 bg-sky-400/[0.025] p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-sky-300">
            Original ASTRA signed notification preflight
          </p>
          <h2 className="mt-2 text-2xl font-semibold">Provider and consent authority</h2>
          <p className="mt-3 text-sm leading-6 text-slate-400">
            Gateway status: {label(data.original_notification_gateway.status)}.
            Research now checks separate provider and identity-owner signatures,
            time-limited consent, original claim ownership and callback nonce scope.
            Real provider and device integrations are not connected.
          </p>
          <p className="mt-3 text-xs text-amber-200">
            Original-owner credentials: Not provisioned · Live callback endpoint:
            Disabled · Notification sent: No · Real device delivery: Unverified
          </p>
        </section>
        <section className="mt-6 rounded-2xl border border-slate-300/20 p-6">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-300">
            Original Identity and consent source
          </p>
          <h2 className="mt-2 text-xl font-semibold">Device reminder authority</h2>
          <p className="mt-3 text-sm text-slate-400">
            Source status: {label(data.original_reminder_identity_source.status)}.
            Prospect opt-in and CRM membership are not verified permission
            to notify a particular device.
          </p>
          <p className="mt-3 text-xs text-amber-200">
            Device consent: Unverified · Real provider: Not connected · Sending: Off
          </p>
        </section>
        <footer className="mt-7 rounded-xl border border-amber-400/20 p-5 text-sm text-slate-400">
          Local-model self-play: {label(data.local_model_selfplay.status)}.
          The existing llama.cpp runtime responded to health checks but the manual
          synthetic inference probe timed out. No successful local-model self-play is claimed.
          Original owner review of access controls and private publication remains mandatory.
          No Gmail, EmpireDB, trading, mail sending or financial mutations.
        </footer>
      </>}
    </div>
  </main>;
}
