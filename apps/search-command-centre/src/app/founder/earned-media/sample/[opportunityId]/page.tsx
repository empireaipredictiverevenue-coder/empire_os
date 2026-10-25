import Link from "next/link";
import { notFound } from "next/navigation";
import { connection } from "next/server";
import { getFounderLeadSamplePreview } from "@/lib/founder-api";

type Params = Promise<{ opportunityId: string }>;

export default async function EarnedMediaSamplePage({ params }: { params: Params }) {
  // These flags do not authenticate a visitor. Deployment must remain held
  // until founder ingress/session enforcement has been independently tested.
  if (
    process.env.EMPIRE_EARNED_MEDIA_FOUNDER_UI_ENABLED !== "1" ||
    process.env.EMPIRE_FOUNDER_CONSOLE_PRIVATE_AUTH_VERIFIED !== "1"
  ) {
    notFound();
  }
  await connection();
  const { opportunityId } = await params;
  if (!/^leadreview_[a-f0-9]{24}$/.test(opportunityId)) notFound();
  const result = await getFounderLeadSamplePreview(opportunityId);
  if (result.status === 404) notFound();
  const sample = result.data;
  return (
    <main className="min-h-screen bg-[#060b18] p-5 text-slate-100 md:p-9">
      <div className="mx-auto max-w-5xl">
        <Link href="/founder/earned-media"
          className="text-xs uppercase tracking-[0.18em] text-cyan-200">
          ← Earned Media Founder Review
        </Link>
        {!result.ok || !sample ? (
          <section className="mt-7 rounded-2xl border border-amber-400/25 p-6">
            <h1 className="text-xl font-semibold">Sample preview held</h1>
            <p className="mt-2 text-sm text-amber-200">
              Source evidence unavailable ({result.reason ?? "unverified"}).
              No client claim or sales authority is implied.
            </p>
          </section>
        ) : (
          <>
            <header className="mt-7 rounded-3xl border border-cyan-300/15 bg-[#0b1225] p-7">
              <p className="text-xs uppercase tracking-[0.18em] text-amber-300">
                Original illustrative sample · internal founder preview
              </p>
              <h1 className="mt-3 text-3xl font-semibold">{sample.title}</h1>
              <p className="mt-2 text-sm text-slate-400">
                Research observation: {sample.label} · {sample.lead_stage.replaceAll("_", " ").toLowerCase()}
              </p>
              <p className="mt-4 text-sm leading-6 text-slate-300">
                {sample.safe_introduction}
              </p>
            </header>
            <div className="mt-5 space-y-3">
              {sample.sections.map((section) => (
                <section key={section.heading}
                  className="rounded-2xl border border-white/10 bg-[#0b1225] p-6">
                  <h2 className="text-lg font-semibold text-cyan-100">{section.heading}</h2>
                  <p className="mt-2 text-sm leading-7 text-slate-300">{section.review_text}</p>
                </section>
              ))}
            </div>
            <section className="mt-6 rounded-2xl border border-amber-400/25 bg-amber-400/5 p-5">
              <h2 className="font-semibold text-amber-200">Human release gates</h2>
              <ul className="mt-3 list-inside list-disc space-y-2 text-xs text-amber-100/90">
                {sample.necessary_human_gates.map((gate) => (
                  <li key={gate}>{gate.replaceAll("_", " ").toLowerCase()}</li>
                ))}
              </ul>
              <p className="mt-4 text-xs text-amber-100">
                No proposal, quote, CRM write, message, publication or payment has occurred.
                Examples are not client case studies and do not establish delivery capability.
              </p>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
