import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Roofing Service Request · Buyer Review",
  description: "Review-only generic roofing acquisition page for buyer approval.",
  robots: { index: false, follow: false },
};

const needs = [
  ["Roof leak or water entry", "Describe where you are seeing the issue and when you first noticed it."],
  ["Storm or wind damage", "Tell us what changed after the weather event and whether the property is secure."],
  ["Missing or damaged materials", "Share the visible roof issue so the service request can be matched appropriately."],
  ["Roof replacement enquiry", "Provide basic property and project details to help identify relevant availability."],
];

const steps = [
  ["01", "Tell us what you need", "Choose the roofing issue that best matches your situation and provide your location."],
  ["02", "Confirm service area", "Availability depends on your location and current provider capacity."],
  ["03", "Start the call", "When an eligible route is available, you choose whether to place the call."],
];

export default function LeadSmartRoofingReviewPage() {
  return (
    <main className="min-h-screen bg-[#F6F3EC] text-[#10251B] [font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,'Segoe_UI',sans-serif]">
      <section className="border-b border-black/10 bg-[#10251B] text-white">
        <div className="mx-auto flex max-w-[1180px] flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <div className="inline-flex w-fit items-center gap-2 rounded-full border border-[#D7B86A]/35 bg-[#D7B86A]/10 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#F0D899]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#F0D899]" />
            Buyer review only · traffic disabled
          </div>
          <p className="text-xs leading-5 text-white/55">
            No live number · no routing · no spend · no publication
          </p>
        </div>
      </section>

      <section className="relative overflow-hidden border-b border-black/10">
        <div className="pointer-events-none absolute inset-0 opacity-[0.045] [background-image:linear-gradient(to_right,#10251B_1px,transparent_1px),linear-gradient(to_bottom,#10251B_1px,transparent_1px)] [background-size:40px_40px]" />
        <div className="relative mx-auto grid max-w-[1180px] gap-12 px-5 py-16 sm:px-8 lg:grid-cols-[1.08fr_.92fr] lg:items-center lg:py-24">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#4C755F]">
              Roofing service information
            </p>
            <h1 className="mt-5 max-w-3xl text-[44px] font-semibold leading-[0.96] tracking-[-0.052em] text-[#10251B] sm:text-[60px] lg:text-[68px]">
              Need help with a roofing issue?
            </h1>
            <p className="mt-6 max-w-[610px] text-[17px] leading-8 text-[#56645B] sm:text-lg">
              Tell us what is happening and where the property is located. Service availability depends on location and provider capacity.
            </p>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <button
                type="button"
                disabled
                className="min-h-11 cursor-not-allowed rounded-xl bg-[#10251B] px-6 py-4 text-sm font-semibold text-white opacity-70"
              >
                Call route pending approval
              </button>
              <a
                href="#how-it-works"
                className="min-h-11 rounded-xl border border-[#10251B]/15 bg-white/75 px-6 py-4 text-center text-sm font-semibold text-[#10251B]"
              >
                See how the request works
              </a>
            </div>

            <p className="mt-4 max-w-xl text-xs leading-5 text-[#758078]">
              Review note: a live tracking number is inserted only after buyer approval, routing verification and campaign-specific qualification rules are confirmed.
            </p>
          </div>

          <aside className="rounded-[28px] border border-black/10 bg-white p-6 shadow-[0_26px_70px_rgba(16,37,27,0.10)] sm:p-8">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#4C755F]">
              Start with the roof issue
            </p>
            <div className="mt-5 grid gap-3">
              {needs.map(([title, detail]) => (
                <div key={title} className="rounded-2xl border border-black/8 bg-[#FBFAF7] p-4">
                  <div className="flex gap-3">
                    <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-[#5F8770]" />
                    <div>
                      <h2 className="text-sm font-semibold text-[#10251B]">{title}</h2>
                      <p className="mt-1 text-sm leading-6 text-[#69746D]">{detail}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </aside>
        </div>
      </section>

      <section id="how-it-works" className="border-b border-black/10 bg-white">
        <div className="mx-auto max-w-[1180px] px-5 py-16 sm:px-8">
          <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#4C755F]">How it works</p>
          <h2 className="mt-3 max-w-2xl text-3xl font-semibold tracking-[-0.04em] text-[#10251B] sm:text-4xl">
            A clear request path. No promises we cannot substantiate.
          </h2>
          <div className="mt-9 grid gap-4 md:grid-cols-3">
            {steps.map(([number, title, body]) => (
              <div key={number} className="rounded-3xl border border-black/8 bg-[#F6F3EC] p-6">
                <p className="font-mono text-xs text-[#708779]">{number}</p>
                <h3 className="mt-5 text-lg font-semibold text-[#10251B]">{title}</h3>
                <p className="mt-2 text-sm leading-6 text-[#69746D]">{body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-black/10">
        <div className="mx-auto grid max-w-[1180px] gap-10 px-5 py-16 sm:px-8 lg:grid-cols-2">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.2em] text-[#4C755F]">Before calling</p>
            <h2 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-[#10251B]">
              Have the basics ready.
            </h2>
            <p className="mt-4 max-w-xl text-sm leading-7 text-[#69746D]">
              A concise description of the roofing issue and property location can help determine whether an eligible service route is available.
            </p>
            <ul className="mt-6 grid gap-3 text-sm leading-6 text-[#46534B]">
              <li>• Property ZIP code or service location</li>
              <li>• Type of roofing issue or project</li>
              <li>• When the issue started or was observed</li>
              <li>• Any immediate access or safety considerations</li>
            </ul>
          </div>

          <div className="rounded-[28px] bg-[#10251B] p-7 text-white sm:p-9">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#A6C8B5]">
              Service request disclosure
            </p>
            <p className="mt-5 text-sm leading-7 text-white/75">
              This page helps a consumer request information about roofing service availability. Availability, service scope, provider participation and call qualification can vary by location and program. No price, saving, completion time, contractor quality or service outcome is promised.
            </p>
          </div>
        </div>
      </section>

      <section className="bg-[#10251B] text-white">
        <div className="mx-auto max-w-[1180px] px-5 py-12 sm:px-8">
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-[#A6C8B5]">
            Buyer review checklist
          </p>
          <div className="mt-5 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {[
              "Generic and unbranded consumer creative",
              "No promotions, discounts or guarantees",
              "No unsupported quality, price or ranking claims",
              "Consumer initiates the call",
              "Traffic remains off until buyer approval",
            ].map((rule) => (
              <div key={rule} className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm leading-6 text-white/75">
                {rule}
              </div>
            ))}
          </div>
          <p className="mt-7 text-xs leading-5 text-white/40">
            REVIEW_ONLY · No publication authority · No live traffic · No commercial terms inferred
          </p>
        </div>
      </section>
    </main>
  );
}
