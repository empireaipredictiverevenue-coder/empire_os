"use client";

import { useEffect, useState, type FormEvent } from "react";

type Readiness = {
  status: "OPTIN_COLLECTION_ENABLED" | string;
  notice_version?: string;
  privacy_notice_url?: string;
  form_name?: string;
  subscription_product?: string;
};
type Receipt = {
  status?: string;
  reference?: string;
  detail?: string;
};

const ENDPOINT = "/v1/consumer-optin/roofing";
const STATUS_ENDPOINT = "/v1/consumer-optin/roofing/status";

/**
 * Fail closed. The public page remains a useful free guide even if the
 * dedicated consumer-consent service, privacy notice or suppression path
 * hasn't yet been independently approved and activated.
 *
 * Subscriber consent is never buyer/referral consent. Do not reuse the
 * business-only /commercial endpoint for a consumer email.
 */
export default function GuideSignup() {
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [trap, setTrap] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<Receipt | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(STATUS_ENDPOINT, { cache: "no-store", signal: controller.signal })
      .then(async r => {
        if (!r.ok) return null;
        return await r.json() as Readiness;
      })
      .then(x => {
        const valid = x?.status === "OPTIN_COLLECTION_ENABLED" &&
          x.notice_version === "roofing-homeowner-updates-v1" &&
          x.subscription_product === "EMPIRE_AI_OWN_BRAND_HOMEOWNER_UPDATES" &&
          x.privacy_notice_url === "/privacy";
        if (!controller.signal.aborted && valid) setReadiness(x);
      })
      .catch(() => {});
    return () => controller.abort();
  }, []);

  async function subscribe(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!readiness || !consent || submitting || !email || trap) return;
    setSubmitting(true);
    setResult(null);
    try {
      const response = await fetch(ENDPOINT, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          offer_slug: "roofing-cost-guide",
          email: email.trim(),
          optional_empire_email_updates: consent,
          optional_named_buyer_referral: false,
          notice_version: readiness.notice_version,
          website: trap,
        }),
      });
      const body = await response.json() as Receipt;
      if (response.ok && body.status === "OPTIN_RECORDED_PENDING_VERIFICATION") {
        setResult({ status: body.status });
        setEmail("");
        setConsent(false);
      } else {
        setResult({ detail: "We couldn't confirm your optional subscription. Please try again later." });
      }
    } catch {
      setResult({ detail: "The email signup is temporarily unavailable. You can still read the guide freely." });
    } finally {
      setSubmitting(false);
    }
  }

  return <section aria-label="Optional homeowner email updates" className="mx-auto max-w-6xl px-5 pb-12 sm:px-8 print:hidden">
    <div className="rounded-3xl border border-[#d5e6f7] bg-white px-7 py-8 sm:p-10">
      <p className="text-xs font-extrabold uppercase tracking-[.18em] text-[#0a64c6]">OPTIONAL HOMEOWNER UPDATES</p>
      <h2 className="mt-3 text-2xl font-extrabold text-[#0b274c]">Keep learning before you hire.</h2>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-[#486480]">
        This guide is free without an email address. An optional Empire AI subscriber list is separate from requests to be contacted by a roofing company.
      </p>
      {readiness ? <form onSubmit={subscribe} className="mt-6 max-w-xl space-y-4">
        <label className="block text-sm font-bold text-[#1a395b]">Email for optional Empire AI homeowner updates
          <input type="email" required maxLength={254} value={email} onChange={e => setEmail(e.target.value)}
            autoComplete="email" className="mt-2 w-full rounded-xl border border-[#b6d1ee] px-4 py-3 font-normal" />
        </label>
        <label className="sr-only" aria-hidden="true">Website<input tabIndex={-1} autoComplete="off" name="website" value={trap} onChange={e=>setTrap(e.target.value)} /></label>
        <label className="flex gap-3 text-sm leading-6 text-[#3b5978]">
          <input type="checkbox" required checked={consent} onChange={e=>setConsent(e.target.checked)}
            className="mt-1 h-4 w-4" />
          <span>I agree to receive optional homeowner guides and related updates by email from Empire AI. I can unsubscribe at any time. This does not permit sharing my details with third-party contractors.</span>
        </label>
        <p className="text-xs text-[#55708e]">Please read our <a href="/privacy" className="underline">privacy notice</a> before subscribing.</p>
        <button type="submit" disabled={!consent || submitting} className="rounded-xl bg-[#086bd0] px-6 py-3 font-bold text-white disabled:opacity-50">
          {submitting ? "Submitting…" : "Join optional email updates"}
        </button>
        {result?.status === "OPTIN_RECORDED_PENDING_VERIFICATION"
          ? <p role="status" className="text-sm text-[#12643d]">We recorded your request. Please look out for any subscription verification message if required.</p>
          : result?.detail ? <p role="alert" className="text-sm text-[#8a2f32]">{result.detail}</p> : null}
      </form> : <p className="mt-5 text-sm leading-7 text-[#55708e]">
        Optional email registration is not open yet. You can read, print or save the entire guide above without sharing personal information.
      </p>}
    </div>
  </section>;
}
