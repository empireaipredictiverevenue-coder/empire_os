"use client";

/** No automatic token consumption: safety scanners follow email links. */
import { useEffect, useState, type FormEvent } from "react";
import Link from "next/link";

type Kind = "confirm" | "unsubscribe";
type Choice = { kind: Kind; token: string } | null;
const PATH = "/v1/consumer-optin/roofing";
const SAFE_TOKEN = /^[a-zA-Z0-9_-]{43}$/;

export default function HomeownerEmailPreferences() {
  const [choice, setChoice] = useState<Choice>(null);
  const [ready, setReady] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<"received" | "unavailable" | null>(null);

  useEffect(() => {
    const readOriginalLink = () => {
      // The token exists ONLY in the fragment, never a server-accessible URL
      // query. Remove the fragment before rendering it in browser memory.
      const hash = window.location.hash.slice(1);
      window.history.replaceState(null, "", window.location.pathname);
      const parts = new URLSearchParams(hash);
      const kind = parts.has("confirm") && !parts.has("unsubscribe")
        ? "confirm"
        : parts.has("unsubscribe") && !parts.has("confirm")
          ? "unsubscribe" : null;
      const secret = kind ? parts.get(kind) : null;
      setChoice(kind && secret && SAFE_TOKEN.test(secret) &&
        [...parts.keys()].length === 1 ? { kind, token: secret } : null);
      setResult(null);
      setReady(true);
    };
    readOriginalLink();
    // Some browsers reuse a tab for another email link to the same page.
    window.addEventListener("hashchange", readOriginalLink);
    return () => window.removeEventListener("hashchange", readOriginalLink);
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!choice || submitting) return;
    setSubmitting(true);
    setResult(null);
    const selected = choice;
    try {
      const response = await fetch(PATH + "/" + selected.kind, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        cache: "no-store",
        body: JSON.stringify({
          [selected.kind === "confirm" ? "confirmation_token" : "unsubscribe_token"]:
            selected.token,
        }),
      });
      setResult(response.status === 202 ? "received" : "unavailable");
    } catch {
      setResult("unavailable");
    } finally {
      // Tokens are never saved in a cookie, local storage or analytics.
      setChoice(null);
      setSubmitting(false);
    }
  }

  const isUnsubscribe = choice?.kind === "unsubscribe";
  return <main className="min-h-screen bg-[#f1f7ff] text-[#092647]">
    <header className="bg-[#062650] px-6 py-6 text-white">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4">
        <Link href="/" className="font-bold tracking-wide">EMPIRE AI</Link>
        <span className="text-xs text-[#b9daff]">Homeowner email preferences</span>
      </div>
    </header>
    <section className="mx-auto max-w-3xl px-6 py-16">
      <div className="rounded-3xl border border-[#bed9f2] bg-white p-8 shadow-[0_15px_50px_rgba(5,43,96,.08)] sm:p-12">
        <p className="text-xs font-extrabold uppercase tracking-[.18em] text-[#086fcd]">
          First-party communications
        </p>
        <h1 className="mt-5 text-3xl font-extrabold tracking-tight sm:text-4xl">
          {isUnsubscribe ? "Stop homeowner email updates" :
            choice?.kind === "confirm" ? "Confirm your subscription" :
            "Your email preferences"}
        </h1>
        <p className="mt-4 text-base leading-8 text-[#466382]">
          Empire AI homeowner updates are optional. Receiving a free roofing guide
          never requires a marketing subscription and doesn't authorise sharing your
          email with a roofing contractor.
        </p>
        {!ready ? <p className="mt-6 text-sm">Checking your request…</p>
          : result === "received" ? <p role="status" className="mt-6 rounded-xl bg-[#e5f6eb] p-5 text-[#12623a]">
            Your request was received. The service will apply it if the link is valid.
          </p>
          : result === "unavailable" ? <p role="alert" className="mt-6 rounded-xl bg-[#fff4ed] p-5 text-[#8b3d1b]">
            We couldn't verify your request right now. Please use the original email link
            again or contact us using the privacy details below.
          </p>
          : choice ? <form onSubmit={submit} className="mt-8">
            <p className="text-sm leading-7 text-[#466382]">
              {isUnsubscribe
                ? "Confirm that you want to stop receiving Empire AI homeowner updates."
                : "Confirm that you want to receive optional Empire AI homeowner updates."}
            </p>
            <button disabled={submitting} type="submit"
              className="mt-5 min-h-12 rounded-xl bg-[#046ccf] px-6 py-3 font-bold text-white disabled:opacity-50">
              {submitting ? "Processing…" :
                isUnsubscribe ? "Unsubscribe from updates" : "Confirm my subscription"}
            </button>
          </form>
          : <p className="mt-6 text-sm leading-7 text-[#466382]">
            No valid preference link was provided. Please open the original message
            again, or contact us through the privacy notice below.
          </p>}
        <p className="mt-10 border-t border-[#e1ebf5] pt-6 text-xs leading-6 text-[#56728f]">
          For privacy questions or requests, see our <Link href="/privacy" className="font-bold underline">
            privacy notice</Link>. Your choice affects Empire AI's own-brand emails,
          not unrelated third-party marketing lists.
        </p>
      </div>
    </section>
  </main>;
}
