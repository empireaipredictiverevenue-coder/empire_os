/**
 * V11 order-specific source-evidence progress, presentation only.
 * The existing private founder API must supply the signed-CRM-authorized,
 * redacted server-side view. This component does NOT fetch, authenticate,
 * retain a bearer or infer revenue from the CRM order status.
 */
export type FounderRevenueCaseView = {
  schema_version: "empire.crm.founder_revenue_case_view.v1";
  status: "SIGNED_ORDER_OBSERVED_FINANCIAL_PROOF_UNATTESTED";
  mode: "OBSERVE";
  case_ref: string;
  reported_order_state: string | null;
  next_missing_stage: string;
  next_original_owner: string;
  next_original_action: string;
  stages: Array<{
    stage: string;
    status: "NOT_OBSERVED" | "SOURCE_REPORTED_COHERENCE_ONLY";
  }>;
  independent_evidence_attested_here: false;
  recognized_revenue_verified_here: false;
  economic_memory_training_authorized: false;
  database_writes: false;
  outbound_sent: false;
  execution_authority: "NONE";
};

function readable(raw: string) {
  return raw.replaceAll("_", " ").toLowerCase();
}

export function RevenueCasePanel({
  caseView,
}: {
  caseView: FounderRevenueCaseView | null;
}) {
  if (!caseView) {
    return (
      <section className="panel" aria-label="Private revenue case">
        <p className="eyebrow">Private revenue evidence</p>
        <h2 className="mt-2 text-xl font-semibold text-white">Order review held</h2>
        <p className="mt-3 text-sm leading-6 text-slate-400">
          The original signed-tenant CRM reader and restricted order RPC must
          pass owner release checks before an actual order can be shown.
          No revenue or delivery is inferred from a CRM status.
        </p>
      </section>
    );
  }

  const verifiedView =
    caseView.schema_version === "empire.crm.founder_revenue_case_view.v1" &&
    caseView.status === "SIGNED_ORDER_OBSERVED_FINANCIAL_PROOF_UNATTESTED" &&
    caseView.mode === "OBSERVE" &&
    caseView.execution_authority === "NONE" &&
    caseView.independent_evidence_attested_here === false &&
    caseView.recognized_revenue_verified_here === false &&
    caseView.economic_memory_training_authorized === false &&
    caseView.database_writes === false &&
    caseView.outbound_sent === false &&
    Array.isArray(caseView.stages) &&
    caseView.stages.length === 5 &&
    caseView.stages.every(
      (row) =>
        typeof row.stage === "string" &&
        (row.status === "NOT_OBSERVED" ||
          row.status === "SOURCE_REPORTED_COHERENCE_ONLY"),
    );

  if (!verifiedView) {
    return (
      <section className="panel" role="status">
        <p className="text-sm text-amber-200">
          Revenue case evidence could not be trusted. No order is displayed.
        </p>
      </section>
    );
  }

  return (
    <section className="panel" aria-label="Revenue case evidence progress">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="eyebrow">Private signed CRM order</p>
          <h2 className="mt-2 text-xl font-semibold text-white">
            Revenue evidence progress
          </h2>
          <p className="mt-2 text-xs text-slate-500">
            Case {caseView.case_ref} · source-reported order state:{" "}
            {caseView.reported_order_state ?? "Unknown"}
          </p>
        </div>
        <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-xs font-semibold text-amber-200">
          Independent payment proof outstanding
        </span>
      </div>
      <ol className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {caseView.stages.map((entry) => (
          <li
            key={entry.stage}
            className="rounded-2xl border border-white/10 bg-white/[0.025] px-4 py-4"
          >
            <p className="text-sm font-semibold capitalize text-slate-100">
              {readable(entry.stage)}
            </p>
            <p className="mt-2 text-xs leading-5 text-slate-400">
              {entry.status === "NOT_OBSERVED"
                ? "Original evidence not observed"
                : "Source coherence only · not externally attested"}
            </p>
          </li>
        ))}
      </ol>
      <div className="mt-5 border-t border-white/10 pt-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-amber-200">
          Next missing step: {readable(caseView.next_missing_stage)}
        </p>
        <p className="mt-2 text-sm text-slate-300">
          Original owner: <strong>{caseView.next_original_owner}</strong>
        </p>
        <p className="mt-1 text-xs text-slate-400">
          {readable(caseView.next_original_action)}
        </p>
        <p className="mt-3 text-xs text-slate-500">
          This view does not certify settlement, revenue recognition or
          Economic Memory learning.
        </p>
      </div>
    </section>
  );
}
