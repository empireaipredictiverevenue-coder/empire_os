import Link from "next/link";
import { connection } from "next/server";
import { getFounderJevStatus } from "@/lib/founder-jev-read";

function label(state: boolean | null | undefined) {
  return state === true ? "Verified" : state === false ? "Not verified" : "Unavailable";
}

function TruthLine({
  title,
  value,
  detail,
}: {
  title: string;
  value: boolean | null | undefined;
  detail: string;
}) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-white">{title}</h3>
        <span
          className={
            value === true
              ? "rounded-full border border-sky-300/30 bg-sky-300/10 px-2.5 py-1 text-[11px] font-semibold text-sky-200"
              : "rounded-full border border-amber-300/20 bg-amber-300/5 px-2.5 py-1 text-[11px] font-semibold text-amber-200"
          }
        >
          {label(value)}
        </span>
      </div>
      <p className="mt-3 text-xs leading-6 text-slate-400">{detail}</p>
    </div>
  );
}

export default async function FounderJevPage() {
  await connection();
  const result = await getFounderJevStatus();
  const state = result.data;
  const present = result.available && state !== null;

  const modelReady = state?.native_compatibility_tested ?? null;
  const economicReader = state?.economic_reader_configured ?? null;
  const crmReader = state?.crm_reader_configured ?? null;
  const replyMigration = state?.reply_candidate_migration_051_applied ?? null;
  const mailboxHeaderReader = state?.owned_imap_header_review_configured ?? null;
  const mailboxCrmVerified = state?.mailbox_crm_alignment_verified ?? null;
  const founderAccess = state?.independent_founder_authorizer_configured ?? null;
  const calibrated = state?.commercial_model_calibrated ?? null;
  const researchCore = state?.shared_vane_openmanus_research_core_integrated ?? null;
  const researchActive = state?.jev_public_research_execution_activated ?? null;
  const researchValidated = state?.jev_research_source_validation_completed_live ?? null;
  const sourceContinuity = state?.jev_official_primary_continuity_implemented ?? null;
  const productionLive = state?.production_activated ?? null;
  const buyerRows = state?.buyers_identified ?? null;
  const canonicalRows = state?.real_canonical_rows_verified ?? null;

  return (
    <main className="min-h-screen bg-[#040919] text-slate-100">
      <div className="mx-auto max-w-7xl px-5 py-8 lg:px-10 lg:py-12">
        <header className="border-b border-sky-200/10 pb-9">
          <Link
            href="/founder"
            className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-300 hover:text-sky-100"
          >
            ← Founder Console
          </Link>
          <div className="mt-9 flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-sky-300">
                Empire AI · Revenue intelligence
              </p>
              <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white md:text-5xl">
                JEV Decision Intelligence
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-400">
                First-party decisions from authenticated evidence. This view
                distinguishes model compatibility, real buyer data and
                production authority. None of them implies realised revenue.
              </p>
            </div>
            <span className="rounded-full border border-amber-300/30 bg-amber-300/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.15em] text-amber-200">
              {present ? (productionLive ? "Production live" : "Observe · gated") : "Source unavailable"}
            </span>
          </div>
        </header>

        {!present || !state ? (
          <section
            role="status"
            className="mt-7 rounded-2xl border border-amber-300/20 bg-amber-300/[0.045] p-6"
          >
            <h2 className="text-lg font-semibold text-white">Live JEV status is unavailable</h2>
            <p className="mt-2 text-sm text-slate-300">
              {result.reason ?? "The Founder JEV read endpoint has not been deployed."}
              {" "}No signals, buyers, outcomes or readiness are inferred from the missing response.
            </p>
          </section>
        ) : (
          <section className="mt-7 grid gap-4 md:grid-cols-3" aria-label="Observed JEV facts">
            <div className="rounded-2xl border border-sky-300/20 bg-sky-300/[0.055] p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-300">
                Local model primitives
              </p>
              <p className="mt-4 text-xl font-semibold text-white">
                {state.native_model_primitives.join(" · ")}
              </p>
              <p className="mt-3 text-xs leading-6 text-slate-400">
                Native compatibility tests do not prove commercial prediction accuracy.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                Canonical economic records
              </p>
              <p className="mt-4 text-2xl font-semibold text-white">
                {canonicalRows == null ? "Unavailable" : canonicalRows.toLocaleString("en-GB")}
              </p>
              <p className="mt-3 text-xs leading-6 text-slate-400">
                Not buyer enquiries or contact permission.
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                Independently verified buyers
              </p>
              <p className="mt-4 text-2xl font-semibold text-white">
                {buyerRows == null ? "Unavailable" : buyerRows.toLocaleString("en-GB")}
              </p>
              <p className="mt-3 text-xs leading-6 text-slate-400">
                Unknown remains unknown until canonical buyer evidence is available.
              </p>
            </div>
          </section>
        )}

        <section className="mt-10" aria-label="Verification gates">
          <div className="mb-5">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-300">
              Release evidence
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight text-white">
              What is complete, and what must still be proven
            </h2>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <TruthLine title="Local typed inference" value={modelReady}
              detail="Choice, Score and Noul have been tested against the local Laya sidecar using synthetic data." />
            <TruthLine title="Dedicated EmpireDB reader" value={economicReader}
              detail="Requires a restricted reader login, database-bound tenant and read-only transaction." />
            <TruthLine title="Canonical CRM prospect review" value={crmReader}
              detail="Reuses the existing tenant-scoped CRM repository. Prospects are research records; missing conversation and closer joins cannot be presented as buyer replies." />
            <TruthLine title="Original reply candidate scope" value={replyMigration}
              detail="Prepared-only EmpireDB 051 adds tenant-restricted reply metadata without message bodies or contact details. Provider authenticity, contact identity and positive buying intent remain unverified." />
            <TruthLine title="First-party mailbox header review" value={mailboxHeaderReader}
              detail="Read-only IMAP header reconciliation uses HMAC references. Explicit founder authority and a separate private HMAC key are required; the review cannot send mail." />
            <TruthLine title="Authenticated CRM-to-mailbox buyer linkage" value={mailboxCrmVerified}
              detail="Matching an RFC parent or reply alias is structural evidence only. Original-provider authentication, tenant/contact binding, buyer intent and suppression still require separate proof." />
            <TruthLine title="Founder access enforcement" value={founderAccess}
              detail="No detailed entity research route is registered unless an independent server-side authorizer is supplied." />
            <TruthLine title="Shared Vane/OpenManus research core" value={researchCore}
              detail="Bounded plans, source-cited discovery and review receipts are implemented. Original OpenManus unrestricted tools are not installed." />
            <TruthLine title="JEV public research operational activation" value={researchActive}
              detail="Offline engineering is separate from production. Requires approved public-only search/inspection policies and independently tested live evidence quality." />
            <TruthLine title="Original-source continuity" value={sourceContinuity}
              detail="Allows explicitly selected GOV.UK and ONS primary pages to be inspected when public search is unavailable; no provider bypass, lead claims or commercial permission." />
            <TruthLine title="Original-source live research quality" value={researchValidated}
              detail="Individual source inspection has been tested. Representative source quality, factual accuracy and buyer-intent validation are not independently complete." />
            <TruthLine title="Commercial model calibration" value={calibrated}
              detail="Requires real independently labelled cases, reliability analysis and comparison with the deterministic baseline." />
            <TruthLine title="Verified buyer conversations"
              value={buyerRows == null ? null : buyerRows > 0}
              detail="Only exact canonical buyer and reply linkage can establish a real commercial conversation." />
            <TruthLine title="Production routing" value={productionLive}
              detail="Outbound governor, founder approval and source security remain separate release gates." />
          </div>
        </section>

        <section className="mt-9 rounded-2xl border border-sky-300/15 bg-sky-300/[0.035] p-6">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-300">
            Next verified milestone
          </p>
          <h2 className="mt-3 text-lg font-semibold text-white">
            Authenticated evidence → reviewed commercial opportunity
          </h2>
          <p className="mt-3 max-w-4xl text-sm leading-7 text-slate-400">
            Connect the already-built restricted reader through the existing
            Founder authentication boundary, verify actual EmpireDB records,
            and independently review buyer identity, reply linkage and model
            quality. Recommendations remain read-only until those checks pass.
          </p>
          <p className="mt-4 text-xs text-slate-500">
            No automatic emails, calls, payments or recognised revenue.
          </p>
        </section>
      </div>
    </main>
  );
}
