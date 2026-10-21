import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { forwardedAccessAssertion, isSshFounderResearchMode, requestPrivateResearch, sshFounderRequestIsLocal, sshFounderServerCredential } from "@/lib/founder-research-internal";
import ResearchWorkbench from "./research-workbench";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

type Catalog = {
  products?: Record<string, { title?: string; description?: string }>;
  markets?: string[];
  niches?: string[];
  private_execution_guardrails?: Record<string, unknown>;
};

export default async function FounderResearchPage() {
  const requestHeaders = await headers();
  if (isSshFounderResearchMode() && !sshFounderRequestIsLocal(requestHeaders)) notFound();
  const assertion = isSshFounderResearchMode()
    ? sshFounderServerCredential(requestHeaders)
    : forwardedAccessAssertion(requestHeaders.get("cf-access-jwt-assertion"));
  const answer = assertion ? await requestPrivateResearch("catalog", assertion) : null;
  const catalog = answer?.ok ? answer.data as Catalog : null;
  return <main className="min-h-screen bg-[#06101e] px-5 py-10 text-white lg:px-12">
    <div className="mx-auto max-w-6xl">
      <Link href="/founder" className="text-sm text-cyan-300 hover:underline">← Founder Console</Link>
      <p className="mt-9 text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">Empire AI · Internal intelligence</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight sm:text-5xl">Empire Research + Empire Agent</h1>
      <p className="mt-4 max-w-3xl text-sm leading-7 text-slate-400">
        Evidence-grounded UK/US research and governed multi-step source workflows.
        This workspace is private, read-only with respect to EmpireDB, and subject to Research-owner editorial approval.
      </p>
      {!catalog ? <div className="mt-8 rounded-2xl border border-amber-400/30 bg-amber-400/[0.04] p-6">
        <h2 className="text-lg font-semibold">Verified Founder session required</h2>
        <p className="mt-2 text-sm text-slate-400">The research workstation is locked until the existing access edge supplies a signed session, the backend verifies its exact Founder subject, and the owner enables the guarded configuration.</p>
        <p className="mt-3 text-xs text-amber-200">{answer?.status === 503 ? "Research identity/service configuration unavailable" : "No verified Founder Research authorisation"}</p>
      </div> : <ResearchWorkbench catalog={catalog} />}
    </div>
  </main>;
}
