import "server-only";

type Candidate = {
  gmail_message_id: string;
  received_at: string;
  state: string;
  contact_identity_verified: false;
  commercial_intent_verified: false;
};

type ReviewItem = {
  company: string;
  gmail_thread_id: string;
  gmail_thread_url: string;
  sent_verified: true;
  inbound_candidate_count: number;
  inbound_candidates: Candidate[];
  founder_action: string;
  crm_conversation_created: false;
  tenant_and_contact_binding_verified: false;
};

type WorkspaceReview = {
  status: "FRESH_WORKSPACE_REVIEW_QUEUE";
  monitored_threads: 6;
  sent_anchors_verified: 6;
  inbound_header_candidate_count: number;
  scanned_at: string;
  items: ReviewItem[];
  crm_conversation_created: false;
  outbound_sent: false;
  execution_authority: "none";
};

const SAFE_COMPANIES = new Set([
  "GB NRG",
  "Perfect Sense Energy",
  "Solar4Good",
  "Sustain Commercial Solar",
  "SOL PV Group",
  "100% Renewables",
]);

const GMAIL_THREAD = /^[a-f0-9]{16,32}$/;
const RECENT_AGE_MS = 20 * 60 * 1000;

function validReview(value: unknown): value is WorkspaceReview {
  if (!value || typeof value !== "object") return false;
  const row = value as Record<string, unknown>;
  if (
    row.status !== "FRESH_WORKSPACE_REVIEW_QUEUE" ||
    row.monitored_threads !== 6 ||
    row.sent_anchors_verified !== 6 ||
    row.crm_conversation_created !== false ||
    row.outbound_sent !== false ||
    row.execution_authority !== "none" ||
    !Array.isArray(row.items) ||
    row.items.length !== 6 ||
    typeof row.inbound_header_candidate_count !== "number" ||
    !Number.isInteger(row.inbound_header_candidate_count) ||
    row.inbound_header_candidate_count < 0 ||
    typeof row.scanned_at !== "string"
  ) return false;

  const observedAt = Date.parse(row.scanned_at);
  if (!Number.isFinite(observedAt) || observedAt > Date.now() ||
      Date.now() - observedAt > RECENT_AGE_MS) return false;

  const seenCompanies = new Set<string>();
  const seenThreads = new Set<string>();
  let candidateTotal = 0;
  for (const item of row.items) {
    if (!item || typeof item !== "object") return false;
    const entry = item as Record<string, unknown>;
    if (
      typeof entry.company !== "string" ||
      !SAFE_COMPANIES.has(entry.company) ||
      seenCompanies.has(entry.company) ||
      typeof entry.gmail_thread_id !== "string" ||
      !GMAIL_THREAD.test(entry.gmail_thread_id) ||
      seenThreads.has(entry.gmail_thread_id) ||
      entry.gmail_thread_url !==
        `https://mail.google.com/mail/u/?authuser=phil%40empire-ai.co.uk#all/${entry.gmail_thread_id}` ||
      entry.sent_verified !== true ||
      entry.crm_conversation_created !== false ||
      entry.tenant_and_contact_binding_verified !== false ||
      typeof entry.inbound_candidate_count !== "number" ||
      !Number.isInteger(entry.inbound_candidate_count) ||
      entry.inbound_candidate_count < 0 ||
      !Array.isArray(entry.inbound_candidates) ||
      entry.inbound_candidates.length !== entry.inbound_candidate_count
    ) return false;
    if (
      entry.founder_action !==
      (entry.inbound_candidate_count > 0
        ? "REVIEW_ACTUAL_GMAIL_MESSAGE_THEN_CANONICAL_IDENTITY"
        : "WAIT_FOR_GENUINE_REPLY")
    ) return false;
    for (const candidate of entry.inbound_candidates) {
      if (!candidate || typeof candidate !== "object") return false;
      const c = candidate as Record<string, unknown>;
      if (
        typeof c.gmail_message_id !== "string" ||
        !GMAIL_THREAD.test(c.gmail_message_id) ||
        typeof c.received_at !== "string" ||
        !Number.isFinite(Date.parse(c.received_at)) ||
        c.state !== "HEADER_CANDIDATE_REQUIRES_FOUNDER_REVIEW" ||
        c.contact_identity_verified !== false ||
        c.commercial_intent_verified !== false
      ) return false;
    }
    candidateTotal += entry.inbound_candidate_count;
    seenCompanies.add(entry.company);
    seenThreads.add(entry.gmail_thread_id);
  }
  return seenCompanies.size === 6 && seenThreads.size === 6 &&
    candidateTotal === row.inbound_header_candidate_count;
}

async function readWorkspaceReview(): Promise<WorkspaceReview | null> {
  const base = process.env.EMPIRE_API_BASE_URL?.trim();
  // Private loopback is the only supported source; no external CRM proxy,
  // cookies, browser token, host header or tenant selector is trusted here.
  if (base !== "http://127.0.0.1:8766") return null;
  try {
    const response = await fetch(
      base + "/v1/founder-mailbox/workspace-solar-reply-review",
      { cache: "no-store", headers: { Accept: "application/json" } },
    );
    if (!response.ok) return null;
    const payload: unknown = await response.json();
    return validReview(payload) ? payload : null;
  } catch {
    return null;
  }
}

export default async function WorkspaceSolarMailReview() {
  const data = await readWorkspaceReview();
  return (
    <section
      aria-label="Workspace Gmail solar outreach review"
      className="mb-5 rounded-3xl border border-cyan-400/20 bg-[#081529]/95 p-5 shadow-xl shadow-black/20"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.17em] text-cyan-300">
            Workspace Gmail · authenticated evidence
          </p>
          <h2 className="mt-2 text-xl font-semibold text-white">
            Commercial outreach tracking
          </h2>
          <p className="mt-2 text-sm text-slate-400">
            Six verified solar outreach threads, checked by the existing
            EmpireOS Gmail monitor. Replies require founder review before any
            CRM identity or sales stage can be assigned.
          </p>
        </div>
        <span className="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-3 py-1.5 text-xs font-medium text-cyan-100">
          Read-only · no auto-send
        </span>
      </div>
      {!data ? (
        <p className="mt-5 rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-3 text-sm text-amber-200">
          Live Workspace review evidence is unavailable or stale. No reply
          status is inferred; the existing CRM and Gmail histories are
          unchanged.
        </p>
      ) : (
        <>
          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            {[
              ["Sent anchors", String(data.sent_anchors_verified)],
              ["Inbound candidates", String(data.inbound_header_candidate_count)],
              ["CRM cases created", "0 · unverified"],
            ].map(([label, value]) => (
              <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.025] px-4 py-3">
                <p className="text-xs text-slate-400">{label}</p>
                <p className="mt-1 text-xl font-semibold text-white">{value}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
            {data.items.map((item) => (
              <article key={item.gmail_thread_id}
                className="flex flex-col justify-between rounded-2xl border border-white/10 bg-[#0a1830]/70 p-4">
                <div>
                  <p className="text-sm font-semibold text-slate-100">{item.company}</p>
                  <p className="mt-2 text-xs text-slate-400">
                    {item.inbound_candidate_count
                      ? `${item.inbound_candidate_count} inbound candidate(s) · human review needed`
                      : "Sent verified · no reply candidate observed"}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    CRM identity and buyer intent not verified
                  </p>
                </div>
                <a href={item.gmail_thread_url} target="_blank"
                  rel="noopener noreferrer"
                  className="mt-3 text-xs font-semibold text-cyan-300 hover:text-cyan-200">
                  Review original Gmail thread →
                </a>
              </article>
            ))}
          </div>
          <p className="mt-3 text-[11px] text-slate-500">
            Provider metadata only · last scan{" "}
            {new Date(data.scanned_at).toLocaleString("en-GB", {
              timeZone: "Europe/London",
              dateStyle: "medium", timeStyle: "short",
            })}{" "}
            UK · no customer contacts, message bodies, CRM writes or revenue claims
            from this panel.
          </p>
        </>
      )}
    </section>
  );
}
