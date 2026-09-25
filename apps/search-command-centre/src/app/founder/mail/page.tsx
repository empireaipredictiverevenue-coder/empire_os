import Link from "next/link";
import { connection } from "next/server";
import {
  getFounderMailboxThread,
  getFounderMailboxThreads,
  type EmpireMailEvent,
  type EmpireMailThread,
} from "@/lib/founder-api";

type MailSearchParams = Promise<{
  filter?: string | string[];
  thread?: string | string[];
  q?: string | string[];
}>;

const FILTERS = [
  { key: "all", label: "All mail" },
  { key: "replies", label: "Replies" },
  { key: "positive", label: "Positive" },
  { key: "questions", label: "Questions" },
  { key: "objections", label: "Objections" },
  { key: "no_reply", label: "No reply" },
  { key: "delivery_failed", label: "Bounced / failed" },
  { key: "suppressed", label: "Suppressed" },
] as const;

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

function dateTime(value?: string | null) {
  if (!value) return "Unknown";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return value;
  return date.toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function filterThreads(rows: EmpireMailThread[], filter: string) {
  switch (filter) {
    case "replies":
      return rows.filter((row) => row.commercial_status === "replied");
    case "positive":
      return rows.filter((row) => row.classification === "positive");
    case "questions":
      return rows.filter((row) => row.classification === "question");
    case "objections":
      return rows.filter((row) => row.classification === "objection");
    case "no_reply":
      return rows.filter((row) => row.commercial_status === "no_reply");
    case "delivery_failed":
      return rows.filter((row) => row.commercial_status === "delivery_failed");
    case "suppressed":
      return rows.filter((row) => row.suppressed === true);
    default:
      return rows;
  }
}

function statusTone(row: EmpireMailThread) {
  if (row.suppressed) {
    return "border-rose-400/30 bg-rose-400/10 text-rose-200";
  }
  if (row.classification === "positive") {
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  }
  if (row.classification === "question") {
    return "border-cyan-400/30 bg-cyan-400/10 text-cyan-200";
  }
  if (row.classification === "objection") {
    return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  }
  if (row.commercial_status === "delivery_failed") {
    return "border-orange-400/30 bg-orange-400/10 text-orange-200";
  }
  if (row.commercial_status === "replied") {
    return "border-violet-400/30 bg-violet-400/10 text-violet-200";
  }
  return "border-white/10 bg-white/[0.04] text-slate-300";
}

function statusLabel(row: EmpireMailThread) {
  if (row.suppressed) return "Suppressed";
  if (row.classification === "positive") return "Positive";
  if (row.classification === "question") return "Question";
  if (row.classification === "objection") return "Objection";
  if (row.commercial_status === "delivery_failed") {
    return row.delivery_state === "bounced" ? "Bounced" : "Failed";
  }
  if (row.commercial_status === "replied") return "Replied";
  return (row.delivery_state ?? "No reply").replaceAll("_", " ");
}

function directionLabel(event: EmpireMailEvent) {
  return event.direction === "inbound" ? "Inbound" : "Outbound";
}

function eventTone(event: EmpireMailEvent) {
  if (event.direction === "inbound") {
    return "border-cyan-400/20 bg-cyan-400/[0.055]";
  }
  return "border-white/10 bg-white/[0.025]";
}

export default async function FounderMailPage({
  searchParams,
}: {
  searchParams: MailSearchParams;
}) {
  await connection();
  const params = await searchParams;
  const activeFilter = first(params.filter) ?? "all";
  const query = (first(params.q) ?? "").trim().toLowerCase();

  const mailboxResult = await getFounderMailboxThreads(80);
  const mailbox = mailboxResult.data;
  const rows = mailbox?.threads ?? [];
  const filtered = filterThreads(rows, activeFilter);
  const visible = query
    ? filtered.filter((row) =>
        [row.contact, row.subject]
          .filter(Boolean)
          .some((value) => String(value).toLowerCase().includes(query)),
      )
    : filtered;

  const requestedThread = first(params.thread);
  const selectedId =
    (requestedThread && rows.some((row) => row.thread_id === requestedThread)
      ? requestedThread
      : visible[0]?.thread_id) ?? null;

  const detailResult = selectedId
    ? await getFounderMailboxThread(selectedId, 80)
    : null;
  const selected =
    detailResult?.ok && detailResult.data
      ? detailResult.data
      : visible.find((row) => row.thread_id === selectedId) ?? null;

  const summary = mailbox?.summary ?? {};

  return (
    <main className="min-h-screen bg-[#060b18] text-slate-100">
      <div className="fixed inset-0 -z-0 bg-[radial-gradient(circle_at_20%_0%,rgba(40,91,255,0.15),transparent_28%),radial-gradient(circle_at_90%_12%,rgba(0,203,255,0.08),transparent_24%)]" />
      <div className="relative z-10 mx-auto max-w-[1800px] px-4 py-5 sm:px-6 lg:px-8">
        <header className="mb-5 flex flex-col gap-4 rounded-3xl border border-white/10 bg-[#0a1124]/90 px-5 py-5 shadow-2xl shadow-black/30 backdrop-blur-xl lg:flex-row lg:items-end lg:justify-between">
          <div>
            <Link
              href="/founder"
              className="text-xs font-semibold uppercase tracking-[0.18em] text-cyan-300 hover:text-cyan-200"
            >
              ← Founder Console
            </Link>
            <div className="mt-4 flex items-center gap-3">
              <div className="grid h-11 w-11 place-items-center rounded-2xl border border-cyan-300/20 bg-cyan-300/10 text-lg font-semibold text-cyan-100">
                EM
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Empire AI · commercial communications
                </p>
                <h1 className="mt-1 text-3xl font-semibold tracking-[-0.04em] text-white">
                  Empire Mail
                </h1>
              </div>
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
              Branded commercial inbox for buyer conversations, delivery truth,
              reply intent and governed next actions. Email activity is never
              presented as realized revenue.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-3 py-1.5 text-xs font-semibold text-cyan-100">
              {mailbox?.identity?.sender_email ?? "Sender identity unavailable"}
            </span>
            <span className="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3 py-1.5 text-xs font-semibold text-emerald-100">
              Read-only · OBSERVE
            </span>
          </div>
        </header>

        {!mailboxResult.ok || !mailbox ? (
          <section className="rounded-3xl border border-amber-400/20 bg-amber-400/[0.05] p-6">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-300">
              Mailbox unavailable
            </p>
            <h2 className="mt-2 text-xl font-semibold text-white">
              Empire Mail could not reach the read API.
            </h2>
            <p className="mt-3 text-sm text-slate-400">
              {mailboxResult.reason ?? "Mailbox data is currently unavailable."}
            </p>
          </section>
        ) : (
          <div className="grid min-h-[760px] overflow-hidden rounded-3xl border border-white/10 bg-[#0a1124]/92 shadow-2xl shadow-black/40 backdrop-blur-xl lg:grid-cols-[220px_minmax(320px,430px)_1fr]">
            <aside className="border-b border-white/10 bg-[#081020]/80 p-4 lg:border-b-0 lg:border-r">
              <div className="mb-5">
                <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Mailbox
                </p>
                <p className="mt-1 text-sm text-slate-300">
                  {summary.all ?? rows.length} tracked threads
                </p>
              </div>

              <nav className="space-y-1">
                {FILTERS.map((filter) => {
                  const count =
                    filter.key === "all"
                      ? summary.all
                      : filter.key === "replies"
                        ? summary.replies
                        : filter.key === "positive"
                          ? summary.positive
                          : filter.key === "questions"
                            ? summary.questions
                            : filter.key === "objections"
                              ? summary.objections
                              : filter.key === "delivery_failed"
                                ? summary.bounced_failed
                                : filter.key === "suppressed"
                                  ? summary.suppressed
                                  : undefined;
                  const active = activeFilter === filter.key;
                  return (
                    <Link
                      key={filter.key}
                      href={{
                        pathname: "/founder/mail",
                        query: { filter: filter.key },
                      }}
                      className={[
                        "flex items-center justify-between rounded-xl px-3 py-2.5 text-sm transition",
                        active
                          ? "bg-blue-500/15 text-blue-100 ring-1 ring-blue-400/20"
                          : "text-slate-400 hover:bg-white/[0.04] hover:text-white",
                      ].join(" ")}
                    >
                      <span>{filter.label}</span>
                      {count != null ? (
                        <span className="text-xs tabular-nums text-slate-500">
                          {count}
                        </span>
                      ) : null}
                    </Link>
                  );
                })}
              </nav>

              <div className="mt-7 rounded-2xl border border-white/8 bg-white/[0.025] p-3">
                <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-slate-500">
                  Provider
                </p>
                <p className="mt-2 text-sm font-medium text-white">Resend</p>
                <p className="mt-1 text-xs leading-5 text-slate-500">
                  Sending + receiving enabled on Empire AI domains.
                </p>
                <p className="mt-2 break-all text-[11px] leading-5 text-slate-600">
                  Reply route: {mailbox.identity?.reply_to ?? "Unknown"}
                </p>
              </div>
            </aside>

            <section className="border-b border-white/10 bg-[#0b1328]/65 lg:border-b-0 lg:border-r">
              <div className="border-b border-white/10 px-4 py-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      {FILTERS.find((row) => row.key === activeFilter)?.label ??
                        "All mail"}
                    </p>
                    <p className="mt-1 text-sm text-slate-300">
                      {visible.length} conversations
                    </p>
                  </div>
                  <span className="rounded-full border border-white/10 bg-white/[0.035] px-2.5 py-1 text-[11px] text-slate-400">
                    Live truth
                  </span>
                </div>
                <form method="get" className="mt-4 flex gap-2">
                  <input type="hidden" name="filter" value={activeFilter} />
                  <input
                    name="q"
                    defaultValue={first(params.q) ?? ""}
                    placeholder="Search contact or subject"
                    className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/15 px-3 py-2 text-xs text-white outline-none placeholder:text-slate-600 focus:border-blue-400/40"
                  />
                  <button
                    type="submit"
                    className="rounded-xl border border-blue-400/20 bg-blue-400/10 px-3 py-2 text-xs font-semibold text-blue-100 hover:bg-blue-400/15"
                  >
                    Search
                  </button>
                </form>
              </div>

              <div className="max-h-[720px] overflow-y-auto">
                {visible.length === 0 ? (
                  <div className="p-8 text-center text-sm text-slate-500">
                    No threads in this view.
                  </div>
                ) : (
                  visible.map((row) => {
                    const active = selectedId === row.thread_id;
                    return (
                      <Link
                        key={row.thread_id}
                        href={{
                          pathname: "/founder/mail",
                          query: {
                            filter: activeFilter,
                            thread: row.thread_id,
                            ...(query ? { q: query } : {}),
                          },
                        }}
                        className={[
                          "block border-b border-white/[0.065] px-4 py-4 transition",
                          active
                            ? "bg-blue-500/10 shadow-[inset_3px_0_0_rgba(96,165,250,0.8)]"
                            : "hover:bg-white/[0.025]",
                        ].join(" ")}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <p className="truncate text-sm font-semibold text-slate-100">
                            {row.contact ?? "Unknown contact"}
                          </p>
                          <span className="shrink-0 text-[11px] text-slate-600">
                            {dateTime(row.latest_at)}
                          </span>
                        </div>
                        <p className="mt-1 line-clamp-1 text-sm text-slate-300">
                          {row.subject ?? "(no subject)"}
                        </p>
                        <div className="mt-3 flex items-center justify-between gap-2">
                          <span
                            className={[
                              "rounded-full border px-2 py-0.5 text-[10px] font-semibold capitalize",
                              statusTone(row),
                            ].join(" ")}
                          >
                            {statusLabel(row)}
                          </span>
                          <span className="truncate text-[10px] uppercase tracking-[0.12em] text-slate-600">
                            {row.next_action?.replaceAll("_", " ") ?? "Unknown"}
                          </span>
                        </div>
                      </Link>
                    );
                  })
                )}
              </div>
            </section>

            <section className="min-w-0 bg-[#091124]/55">
              {selected ? (
                <>
                  <div className="border-b border-white/10 px-5 py-5 lg:px-7">
                    <div className="flex flex-col justify-between gap-4 xl:flex-row xl:items-start">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Commercial thread
                        </p>
                        <h2 className="mt-2 truncate text-2xl font-semibold tracking-[-0.03em] text-white">
                          {selected.subject ?? "(no subject)"}
                        </h2>
                        <p className="mt-2 text-sm text-slate-400">
                          {selected.contact ?? "Unknown contact"}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <span
                          className={[
                            "rounded-full border px-3 py-1 text-xs font-semibold",
                            statusTone(selected),
                          ].join(" ")}
                        >
                          {statusLabel(selected)}
                        </span>
                        {selected.intent_id ? (
                          <span className="rounded-full border border-blue-400/20 bg-blue-400/[0.07] px-3 py-1 text-xs font-semibold text-blue-200">
                            Intent linked
                          </span>
                        ) : (
                          <span className="rounded-full border border-amber-400/20 bg-amber-400/[0.07] px-3 py-1 text-xs font-semibold text-amber-200">
                            Legacy / unlinked
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                      <Meta
                        label="Commercial status"
                        value={selected.commercial_status ?? "Unknown"}
                      />
                      <Meta
                        label="Next governed action"
                        value={selected.next_action ?? "Unknown"}
                      />
                      <Meta
                        label="Delivery"
                        value={selected.delivery_state ?? "Unknown"}
                      />
                      <Meta
                        label="Suppression"
                        value={
                          selected.suppressed
                            ? selected.suppression_origin ?? "Observed"
                            : "None observed"
                        }
                      />
                    </div>
                  </div>

                  <div className="max-h-[610px] space-y-4 overflow-y-auto p-5 lg:p-7">
                    {(selected.events ?? []).length === 0 ? (
                      <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-5 text-sm text-slate-500">
                        Timeline detail is unavailable for this thread.
                      </div>
                    ) : (
                      (selected.events ?? []).map((event, index) => (
                        <article
                          key={event.provider_id ?? String(index)}
                          className={[
                            "rounded-2xl border p-5",
                            eventTone(event),
                          ].join(" ")}
                        >
                          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">
                                  {directionLabel(event)}
                                </span>
                                {event.untrusted_content ? (
                                  <span className="rounded-full border border-amber-400/20 bg-amber-400/[0.06] px-2 py-0.5 text-[10px] font-semibold text-amber-200">
                                    Untrusted inbound
                                  </span>
                                ) : null}
                              </div>
                              <p className="mt-2 text-sm font-medium text-white">
                                {event.direction === "inbound"
                                  ? event.from ?? "Unknown sender"
                                  : (event.to ?? []).join(", ") ||
                                    "Unknown recipient"}
                              </p>
                            </div>
                            <p className="text-xs text-slate-500">
                              {dateTime(event.occurred_at)}
                            </p>
                          </div>

                          <div className="mt-4 rounded-xl border border-white/[0.07] bg-black/10 p-4">
                            <p className="whitespace-pre-wrap break-words text-sm leading-6 text-slate-300">
                              {event.body_text ??
                                "Message body unavailable from the current read model."}
                            </p>
                          </div>

                          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                            <span>
                              {event.delivery_state?.replaceAll("_", " ") ??
                                "state unknown"}
                            </span>
                            {event.classification &&
                            event.classification !== "unknown" ? (
                              <>
                                <span>·</span>
                                <span className="capitalize">
                                  {event.classification}
                                </span>
                              </>
                            ) : null}
                          </div>
                        </article>
                      ))
                    )}
                  </div>

                  <div className="border-t border-white/10 bg-[#07101f]/90 px-5 py-4 lg:px-7">
                    <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
                      <div>
                        <p className="text-xs font-semibold text-slate-300">
                          Governed reply path
                        </p>
                        <p className="mt-1 text-xs text-slate-500">
                          Draft/reasoning only. Live send authority is not exposed
                          by Empire Mail v1.
                        </p>
                      </div>
                      <span className="rounded-xl border border-white/10 bg-white/[0.035] px-4 py-2 text-xs font-semibold text-slate-400">
                        Compose coming after read-model verification
                      </span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="grid min-h-[620px] place-items-center p-8 text-center">
                  <div>
                    <div className="mx-auto grid h-14 w-14 place-items-center rounded-2xl border border-blue-400/20 bg-blue-400/10 text-blue-100">
                      EM
                    </div>
                    <h2 className="mt-4 text-xl font-semibold text-white">
                      Select a conversation
                    </h2>
                    <p className="mt-2 text-sm text-slate-500">
                      Choose a thread to inspect delivery truth, reply intent and
                      governed next action.
                    </p>
                  </div>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </main>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-white/[0.025] px-4 py-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-600">
        {label}
      </p>
      <p className="mt-1 truncate text-xs font-semibold capitalize text-slate-300">
        {value.replaceAll("_", " ")}
      </p>
    </div>
  );
}
